#!/usr/bin/env python3
"""Decisive Noisy-Data Benchmark on Majority5.

Tests whether high complexity ratios (static_100) suffer from overfitting / code bloat
when trained on noisy labels compared to parsimonious (static_14) or dynamic (K5) search.
Also tests the search-then-rerank strategy (search at r=100, re-rank final pool at r=14).

Procedure:
  1. Generate 32-row ground-truth table for majority5.
  2. For each seed, inject label noise (e.g., 10% = 3 flipped rows) into the training table.
  3. Run MOSES on the noisy table using each arm.
  4. Parse the learned final model(s) and evaluate on the clean ground-truth table.
  5. Record train raw, test raw (generalization error), literals, and runtime.
"""
import argparse
import csv
import itertools
import json
import os
import random
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moses_runner_common import (FLOAT, PETTA_RUNNER, REPO_DIR, git_commit,
                                 load_json, parse_output, save_atomic)

OUTPUT_FILE = os.path.join(REPO_DIR, "noisy_benchmark_results.json")
SCRATCH_DIR = os.path.join(REPO_DIR, "scratch")

K5 = ["--stallThresholdK=5", "--relaxWindowMinM=3", "--relaxGraceG=2", "--relaxCooldownC=3"]
ARMS = {
    "static_14": ["--complexityRatio=14.0", "--stallRelaxationMode=False"],
    "static_100": ["--complexityRatio=100.0", "--stallRelaxationMode=False"],
    "stall_relax_K5": ["--stallRelaxationMode=dynamic", "--baseComplexityRatio=14.0",
                       "--relaxedComplexityRatio=100.0"] + K5,
}


def get_majority5_ground_truth():
    rows = []
    for combo in itertools.product([0, 1], repeat=5):
        out = 1 if sum(combo) >= 3 else 0
        rows.append(list(combo) + [out])
    return rows


def generate_noisy_csv(noise_rate, seed, ground_truth):
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    rng = random.Random(seed * 10007 + int(noise_rate * 100))
    n_rows = len(ground_truth)
    k_flips = max(1, round(n_rows * noise_rate))
    flip_indices = set(rng.sample(range(n_rows), k_flips))

    csv_path = os.path.join(SCRATCH_DIR, f"maj5_noisy_nr{int(noise_rate*100)}_s{seed}.csv")
    header = ["X1", "X2", "X3", "X4", "X5", "Out"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for idx, row in enumerate(ground_truth):
            r = list(row)
            if idx in flip_indices:
                r[-1] = 1 - r[-1]
            writer.writerow(r)
    return csv_path, flip_indices


def eval_metta_tree(tree_str, inputs):
    tokens = tree_str.replace("(", " ( ").replace(")", " ) ").split()

    def parse_tokens(toks):
        t = toks.pop(0)
        if t == "(":
            sub = []
            while toks[0] != ")":
                sub.append(parse_tokens(toks))
            toks.pop(0)
            return sub
        return t

    ast = parse_tokens(tokens)

    def evaluate(node):
        if isinstance(node, str):
            if node in inputs:
                return inputs[node]
            if node.lower() == "true":
                return True
            if node.lower() == "false":
                return False
            raise ValueError(f"Unknown literal: {node}")
        op = node[0]
        if op == "NOT":
            return not evaluate(node[1])
        if op == "AND":
            return all(evaluate(child) for child in node[1:])
        if op == "OR":
            return any(evaluate(child) for child in node[1:])
        raise ValueError(f"Unknown op: {op}")

    return evaluate(ast)


def count_tree_literals(tree_str):
    tokens = tree_str.replace("(", " ").replace(")", " ").split()
    return sum(1 for t in tokens if re.match(r"^X\d+$", t))


def evaluate_candidates(final_result_str, ground_truth):
    """Parses candidates from (FinalResult (((<tree> <raw>) ...))) and evaluates on clean ground truth."""
    pairs = re.findall(r"\(\((.*?)\)\s+([-+]?\d*\.?\d+)\)", final_result_str)
    if not pairs:
        return None, []
    
    evaluated = []
    for tree_str, train_raw in pairs:
        tree_str = tree_str.strip()
        tr = float(train_raw)
        lits = count_tree_literals(tree_str)
        # Evaluate on clean ground truth
        test_correct = 0
        try:
            for row in ground_truth:
                inp = {f"X{i+1}": bool(row[i]) for i in range(5)}
                pred = eval_metta_tree(tree_str, inp)
                if pred == bool(row[-1]):
                    test_correct += 1
            test_raw = -(len(ground_truth) - test_correct)
        except Exception:
            test_raw = -len(ground_truth)
            test_correct = 0

        evaluated.append({
            "tree": tree_str,
            "train_raw": tr,
            "test_raw": test_raw,
            "test_correct": test_correct,
            "test_error": len(ground_truth) - test_correct,
            "literals": lits,
            "pen_14": tr - lits / 14.0,
            "pen_100": tr - lits / 100.0,
        })
    return evaluated[0], evaluated


def run_one_noisy_trial(arm, seed, noise_rate, max_gen, timeout, ground_truth, commit="unknown"):
    csv_path, flipped = generate_noisy_csv(noise_rate, seed, ground_truth)
    flags = ARMS[arm]
    cmd = ["bash", PETTA_RUNNER, "moses.metta", "-s", f"--inputFile={csv_path}", "--targetFeature=Out",
           f"--maxGen={max_gen}", "--hcScoreImprovedThreshold=0.5", "--maxRevisits=1", f"--seed={seed}"] + flags

    rec = {
        "problem": "majority5_noisy",
        "arm": arm,
        "seed": seed,
        "noise_rate": noise_rate,
        "n_flips": len(flipped),
        "max_gen": max_gen,
        "commit": commit,
        "timestamp": time.time()
    }

    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=timeout)
        out = proc.stdout or ""
        rec["wall_time"] = time.time() - t0
        rec.update(parse_output(out))
        rec["status"] = "ok" if rec["best_raw"] is not None else "parse_error"
    except subprocess.TimeoutExpired as e:
        rec["wall_time"] = time.time() - t0
        rec["status"] = "timeout"
        out = e.stdout or ""
        rec.update(parse_output(out))
    except Exception as e:
        rec["wall_time"] = time.time() - t0
        rec["status"] = "error"
        rec["error_msg"] = str(e)
        return rec, None

    # Evaluate final top trees on clean ground truth
    m_final = re.search(r"\(FinalResult\s*\((.*?)\)\)\n", out, re.DOTALL)
    top_cand, all_cands = evaluate_candidates(m_final.group(1) if m_final else "", ground_truth)

    if top_cand:
        rec["top_tree"] = top_cand["tree"]
        rec["train_raw"] = top_cand["train_raw"]
        rec["test_raw"] = top_cand["test_raw"]
        rec["test_error"] = top_cand["test_error"]
        rec["literals"] = top_cand["literals"]
        rec["test_perfect"] = bool(top_cand["test_raw"] == 0.0)
    else:
        rec["train_raw"] = rec.get("best_raw")
        rec["test_raw"] = None
        rec["test_error"] = None
        rec["test_perfect"] = False

    # Also compute search-then-rerank result for static_100
    rerank_rec = None
    if arm == "static_100" and all_cands:
        # Re-rank candidates by pen_14
        best_reranked = max(all_cands, key=lambda c: (c["pen_14"], c["train_raw"], -c["literals"]))
        rerank_rec = dict(rec)
        rerank_rec["arm"] = "static_100_rerank14"
        rerank_rec["top_tree"] = best_reranked["tree"]
        rerank_rec["train_raw"] = best_reranked["train_raw"]
        rerank_rec["test_raw"] = best_reranked["test_raw"]
        rerank_rec["test_error"] = best_reranked["test_error"]
        rerank_rec["literals"] = best_reranked["literals"]
        rerank_rec["test_perfect"] = bool(best_reranked["test_raw"] == 0.0)

    return rec, rerank_rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--noise-rate", type=float, default=0.10, help="fraction of labels flipped (default: 0.10 = 3 rows)")
    ap.add_argument("--max-gen", type=int, default=15, help="maxGen (default: 15)")
    ap.add_argument("--timeout", type=int, default=300, help="timeout per run in seconds")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 21)), help="seed list (default: 1..20)")
    ap.add_argument("--arms", nargs="+", default=list(ARMS.keys()), help="arms to run")
    ap.add_argument("--output-file", default=OUTPUT_FILE, help="output JSON file")
    a = ap.parse_args()

    ground_truth = get_majority5_ground_truth()
    commit = git_commit()
    existing = load_json(a.output_file)
    done_keys = {(r.get("arm"), r.get("seed"), r.get("noise_rate")) for r in existing if r.get("status") == "ok"}

    jobs = [(arm, s) for s in a.seeds for arm in a.arms if (arm, s, a.noise_rate) not in done_keys]
    print(f"Noisy Benchmark on Majority5 ({int(a.noise_rate*100)}% noise): {len(jobs)} jobs to execute.")

    results = list(existing)
    for arm, s in jobs:
        print(f"Running {arm} seed={s} noise={a.noise_rate}...", end=" ", flush=True)
        rec, rerank_rec = run_one_noisy_trial(arm, s, a.noise_rate, a.max_gen, a.timeout, ground_truth, commit=commit)
        results = [r for r in results if not (r.get("arm") == arm and r.get("seed") == s and r.get("noise_rate") == a.noise_rate)]
        results.append(rec)
        if rerank_rec:
            results = [r for r in results if not (r.get("arm") == rerank_rec["arm"] and r.get("seed") == s and r.get("noise_rate") == a.noise_rate)]
            results.append(rerank_rec)
        save_atomic(results, a.output_file)
        print(f"TrainRaw={rec.get('train_raw')} TestRaw={rec.get('test_raw')} Lits={rec.get('literals')} ({rec.get('wall_time', 0):.1f}s)")
        if rerank_rec:
            print(f"  -> [Rerank14] TestRaw={rerank_rec.get('test_raw')} Lits={rerank_rec.get('literals')}")


if __name__ == "__main__":
    main()
