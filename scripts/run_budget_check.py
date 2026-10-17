#!/usr/bin/env python3
"""Step 1: parity4 budget check (1x vs 3x generation budget) under static_100 and stall_relax_K5.

Fixes: completed-key bug (1x rows used to mark 3x runs done), maxGen now derived from the
original sweep (3 x its maxGen) instead of a hard-coded 45, optional fresh 1x re-run with the
identical commit/flags, timeouts keep partial results, termination reason inferred from data.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moses_runner_common import (REPO_DIR, STALL_FILE, git_commit, infer_max_gen, load_json,  # noqa: E402
                                 run_campaign, run_one, save_atomic)

OUTPUT_FILE = os.path.join(REPO_DIR, "budget_check_results.json")
ARMS = {
    "static_100": ["--complexityRatio=100.0", "--stallRelaxationMode=False"],
    "stall_relax_K5": ["--stallRelaxationMode=dynamic", "--baseComplexityRatio=14.0",
                       "--relaxedComplexityRatio=100.0", "--stallThresholdK=5", "--relaxWindowMinM=3",
                       "--relaxGraceG=2", "--relaxCooldownC=3"],
}
SEEDS = list(range(1, 11))
PROBLEM = "parity4"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-max-gen", type=int, default=None, help="1x maxGen (default: from the stall sweep)")
    ap.add_argument("--multiplier", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--rerun-1x", action="store_true",
                    help="re-run the 1x arm now (same commit/flags) instead of importing old rows (recommended)")
    ap.add_argument("--seeds", type=int, nargs="+", default=None, help="override seed list (e.g. for dry runs)")
    ap.add_argument("--output-file", default=OUTPUT_FILE, help="override output JSON file")
    a = ap.parse_args()

    seeds = a.seeds if a.seeds is not None else SEEDS
    out_file = a.output_file

    base = a.base_max_gen or infer_max_gen(PROBLEM, arms=set(ARMS) | {"static_14"})
    if base is None:
        sys.exit("Cannot infer the 1x maxGen from the stall sweep; pass --base-max-gen explicitly.")
    mults = {1: base, a.multiplier: base * a.multiplier}
    print(f"1x maxGen={base}, {a.multiplier}x maxGen={base * a.multiplier}")

    existing = load_json(out_file)
    if not a.rerun_1x and not any(r.get("budget_multiplier") == 1 for r in existing):
        imported = 0
        for r in load_json(STALL_FILE):
            if r.get("problem") == PROBLEM and r.get("arm") in ARMS and r.get("seed") in seeds \
                    and r.get("max_gen") == base and r.get("status") == "ok":
                c = dict(r)
                c["budget_multiplier"] = 1
                c["imported_from_stall_sweep"] = True
                existing.append(c)
                imported += 1
        print(f"Imported {imported} 1x rows. VERIFY that the K5 flags of the original sweep match ARMS above.")
        save_atomic(existing, out_file)

    run_mults = sorted(mults) if a.rerun_1x else [a.multiplier]
    commit = git_commit()
    jobs = [{"key": (arm, seed, m), "arm": arm, "seed": seed, "mult": m}
            for seed in seeds for arm in ARMS for m in run_mults]  # seed-major


    def run_fn(j):
        return run_one(PROBLEM, j["arm"], ARMS[j["arm"]], j["seed"], mults[j["mult"]], a.timeout,
                       breakout_fn=lambda raw: raw >= -2.0,
                       extra={"budget_multiplier": j["mult"]}, commit=commit)

    run_campaign(jobs, run_fn, out_file, existing, workers=a.workers)



if __name__ == "__main__":
    main()