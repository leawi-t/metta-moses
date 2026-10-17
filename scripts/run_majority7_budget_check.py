#!/usr/bin/env python3
"""Majority7 budget check (1x vs 3x generation budget) across static_14, static_100, and stall_relax_K5.

Tests whether the -19 plateau observed in Phase 0 was a budget truncation artifact
(capped at 5 generations) or a true topological dead end.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moses_runner_common import (REPO_DIR, git_commit, load_json, run_campaign,
                                 run_one)

OUTPUT_FILE = os.path.join(REPO_DIR, "majority7_budget_check_results.json")
K5 = ["--stallThresholdK=5", "--relaxWindowMinM=3", "--relaxGraceG=2", "--relaxCooldownC=3"]
ARMS = {
    "static_14": ["--complexityRatio=14.0", "--stallRelaxationMode=False"],
    "static_100": ["--complexityRatio=100.0", "--stallRelaxationMode=False"],
    "stall_relax_K5": ["--stallRelaxationMode=dynamic", "--baseComplexityRatio=14.0",
                       "--relaxedComplexityRatio=100.0"] + K5,
}
SEEDS = list(range(1, 11))
PROBLEM = "majority7"
BASE_MAX_GEN = 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-max-gen", type=int, default=BASE_MAX_GEN, help="1x maxGen (default: 5)")
    ap.add_argument("--multiplier", type=int, default=3, help="budget multiplier (default: 3)")
    ap.add_argument("--timeout", type=int, default=900, help="timeout per run in seconds")
    ap.add_argument("--workers", type=int, default=1, help="number of parallel workers (use 1 for majority7 to prevent OOM)")
    ap.add_argument("--seeds", type=int, nargs="+", default=None, help="override seeds")
    ap.add_argument("--arms", nargs="+", default=None, help="override arms")
    ap.add_argument("--multipliers", type=int, nargs="+", default=None, help="multipliers to run (e.g. 1 3)")
    ap.add_argument("--output-file", default=OUTPUT_FILE, help="override output JSON file")
    a = ap.parse_args()

    seeds = a.seeds if a.seeds is not None else SEEDS
    arms = {k: ARMS[k] for k in a.arms} if a.arms else ARMS
    mults_to_run = a.multipliers if a.multipliers is not None else [1, a.multiplier]
    out_file = a.output_file

    gen_map = {m: a.base_max_gen * m for m in mults_to_run}
    for m in mults_to_run:
        print(f"{m}x maxGen = {gen_map[m]}")

    existing = load_json(out_file)
    commit = git_commit()

    jobs = [{"key": (arm, seed, m), "arm": arm, "seed": seed, "mult": m}
            for seed in seeds for arm in arms for m in mults_to_run]  # seed-major

    def run_fn(j):
        return run_one(PROBLEM, j["arm"], arms[j["arm"]], j["seed"], gen_map[j["mult"]], a.timeout,
                       breakout_fn=lambda raw: raw > -19.0,
                       extra={"budget_multiplier": j["mult"]}, commit=commit)

    run_campaign(jobs, run_fn, out_file, existing, workers=a.workers)


if __name__ == "__main__":
    main()
