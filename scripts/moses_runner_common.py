#!/usr/bin/env python3
"""Shared helpers for the metta-moses experiment runners.

Fixes relative to the per-script copies:
  * results are keyed by (arm, seed, budget_multiplier), so 1x rows can never
    mark 3x runs as "already completed";
  * a run with no parsable score is status="parse_error", never a -1e9 "ok" row;
  * timeouts keep their partial output (censored rows) instead of being lost;
  * the termination reason is inferred from data, not assumed;
  * jobs are scheduled seed-major (all arms of a seed run together), so machine
    load drift does not line up with one arm;
  * non-ok rows are replaced on re-run instead of duplicated;
  * git commit, flags and timestamp are stored with every row.
"""
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_DIR = os.environ.get("MOSES_REPO", "/home/nonplds/projects/metta-projects/metta-moses-representation")
PETTA_RUNNER = os.environ.get("PETTA_RUNNER", "/home/nonplds/projects/metta-projects/PeTTa/run.sh")
STALL_FILE = os.path.join(REPO_DIR, "stall_relaxation_results.json")

FLOAT = r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR, capture_output=True,
                              text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _g(pattern, text, default, cast):
    m = re.search(pattern, text)
    if m:
        try:
            return cast(m.group(1))
        except Exception:
            pass
    return default


def parse_output(out):
    if isinstance(out, bytes):
        out = out.decode("utf-8", errors="replace")
    r = {"best_raw": None, "best_pen": None, "literals": 0, "expansions": 0, "unique_visited": 0,
         "relaxed_gens": 0, "fraction_relaxed": 0.0, "switch_count": 0, "total_evals": 0,
         "final_rescored_raw": None, "raw_trajectory": [], "evals_trajectory": []}
    m = re.search(r"\(Step2-Summary (.*?)\)", out)
    if m:
        s = m.group(1)
        r["unique_visited"] = _g(r"UniqueVisited:\s*(\d+)", s, 0, int)
        r["expansions"] = _g(r"TotalExpansions:\s*(\d+)", s, 0, int)
        r["best_raw"] = _g(r"BestRaw:\s*" + FLOAT, s, None, float)
        r["relaxed_gens"] = _g(r"RelaxedGens:\s*(\d+)", s, 0, int)
        r["fraction_relaxed"] = _g(r"FractionRelaxed:\s*" + FLOAT, s, 0.0, float)
        r["switch_count"] = _g(r"SwitchCount:\s*(\d+)", s, 0, int)
        r["termination"] = _g(r"Termination:\s*(\w+)", s, None, str)
    ever = [float(x) for x in re.findall(r"\(Step2-BestRaw Gen: \d+ Exp: \d+ Ever: " + FLOAT, out)]
    if r["best_raw"] is None and ever:
        r["best_raw"] = ever[-1]
    gens = re.findall(r"\(Step2-GenStats Gen: \d+ Exp: \d+ BestRaw: " + FLOAT +
                      r" Literals: (\d+) BestPen: " + FLOAT, out)
    if gens:
        r["literals"] = int(gens[-1][1])
        r["best_pen"] = float(gens[-1][2])
        if not r["expansions"]:
            r["expansions"] = len(gens)
    evals = [int(x) for x in re.findall(r"\(OptimizedDeme:\s*(\d+)\)", out)]
    r["total_evals"] = sum(evals) if evals else 0
    cum_evals = []
    c = 0
    for e in evals:
        c += e
        cum_evals.append(c)
    min_len = min(len(ever), len(cum_evals))
    r["raw_trajectory"] = ever[:min_len]
    r["evals_trajectory"] = cum_evals[:min_len]
    mf = re.search(r"\(FinalResult\s*\(\(\((.*?)\)\s*([-+]?\d+)\)", out)
    r["final_rescored_raw"] = float(mf.group(2)) if mf else r["best_raw"]
    return r


def run_one(problem, arm, flags, seed, max_gen, timeout, breakout_fn, extra=None, commit="unknown"):
    cmd = ["bash", PETTA_RUNNER, "moses.metta", "-s", f"--problem={problem}", f"--maxGen={max_gen}",
           "--hcScoreImprovedThreshold=0.5", "--maxRevisits=1", f"--seed={seed}"] + list(flags)
    rec = {"problem": problem, "arm": arm, "seed": seed, "max_gen": max_gen, "flags": cmd[4:],
           "commit": commit, "timestamp": time.time()}
    rec.update(extra or {})
    t0 = time.time()
    out, status = "", "ok"
    try:
        proc = subprocess.run(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=timeout)
        out = proc.stdout or ""
        if proc.returncode != 0:
            rec["returncode"] = proc.returncode
            rec["stderr_tail"] = (proc.stderr or "")[-500:]
    except subprocess.TimeoutExpired as e:
        raw = e.stdout or ""
        out = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
        status = "timeout"
    except Exception as e:  # noqa: BLE001
        rec.update({"status": "error", "error_msg": str(e), "wall_time": time.time() - t0})
        return rec
    rec["wall_time"] = time.time() - t0
    rec.update(parse_output(out))
    if status == "timeout":
        rec["censored"] = True
    elif rec["best_raw"] is None:
        status = "parse_error"
    rec["status"] = status
    br = rec["best_raw"]
    rec["solved"] = bool(br is not None and br == 0.0)
    rec["breakout"] = bool(br is not None and breakout_fn(br))
    if status == "timeout":
        rec["termination"] = "timeout"
    elif rec.get("termination") and rec["termination"] != "unknown":
        pass
    elif rec["solved"]:
        rec["termination"] = "solved"
    elif rec["expansions"] >= max_gen:
        rec["termination"] = "max_gen_reached"
    elif rec["expansions"] > 0:
        rec["termination"] = "stopped_before_max_gen"
    else:
        rec["termination"] = "unknown"
    return rec



def save_atomic(data, path):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def load_json(path):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return []
    return []


def rec_key(r):
    return (r.get("arm"), r.get("seed"), r.get("budget_multiplier", 1))


def infer_max_gen(problem, stall_path=STALL_FILE, arms=None):
    """maxGen used by the original sweep for `problem`; None if unknown/inconsistent."""
    vals = {r.get("max_gen") for r in load_json(stall_path)
            if r.get("problem") == problem and r.get("max_gen") is not None
            and (arms is None or r.get("arm") in arms)}
    return vals.pop() if len(vals) == 1 else None


def run_campaign(jobs, run_fn, out_path, existing, workers=2):
    """jobs: list of dicts with a 'key' (arm, seed, mult). Seed-major order is the caller's job."""
    done = {rec_key(r) for r in existing if r.get("status") == "ok"}
    todo = [j for j in jobs if j["key"] not in done]
    print(f"{len(todo)} runs to execute, {len(jobs) - len(todo)} already complete.")
    results = list(existing)
    if not todo:
        return results
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run_fn, j): j for j in todo}
        for fut in as_completed(futs):
            j = futs[fut]
            res = fut.result()
            results = [r for r in results if rec_key(r) != j["key"]]
            results.append(res)
            save_atomic(results, out_path)
            print(f"[{res.get('status', '?').upper()}] {res['problem']} {res['arm']} s={res['seed']} "
                  f"x{res.get('budget_multiplier', 1)} raw={res.get('best_raw')} "
                  f"term={res.get('termination')} evals={res.get('total_evals', 0)} "
                  f"({res.get('wall_time', 0):.1f}s)", flush=True)
    return results