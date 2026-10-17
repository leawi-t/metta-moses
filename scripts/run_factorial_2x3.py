#!/usr/bin/env python3
"""Candidate Generator Factorial Benchmark on Parity4 at Extended Budget.

Design:
  Factor A (Candidate Generator):
    - original: --permPolarityMode=classic
    - full_negation: --permPolarityMode=symmetric
  Factor B (Complexity Ratio Arm):
    - static_100: --complexityRatio=100.0, --stallRelaxationMode=False
    - stall_relax_K5: dynamic stall relaxation with K=5
    - (optional) static_14: baseline parsimony

Features:
  - Supports 2x2 factorial: {original, full_negation} x {static_100, stall_relax_K5}
  - Extended budget: --max-gen 45 (or customizable)
  - Trajectory logging at equal evaluations
  - Seed-major scheduling and safe crash/timeout handling
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moses_runner_common import (REPO_DIR, git_commit, load_json, run_campaign,
                                 run_one)

OUTPUT_FILE = os.path.join(REPO_DIR, "factorial_2x3_results.json")
GENERATORS = {
    "original": ["--permPolarityMode=classic"],
    "full_negation": ["--permPolarityMode=symmetric"],
}
K5 = ["--stallThresholdK=5", "--relaxWindowMinM=3", "--relaxGraceG=2", "--relaxCooldownC=3"]
RATIO_ARMS = {
    "static_100": ["--complexityRatio=100.0", "--stallRelaxationMode=False"],
    "stall_relax_K5": ["--stallRelaxationMode=dynamic", "--baseComplexityRatio=14.0",
                       "--relaxedComplexityRatio=100.0"] + K5,
    "static_14": ["--complexityRatio=14.0", "--stallRelaxationMode=False"],
}
DEFAULT_SEEDS = list(range(1, 21))
PROBLEM = "parity4"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-gen", type=int, default=45, help="maxGen horizon (default: 45 for 3x extended budget)")
    ap.add_argument("--timeout", type=int, default=1800, help="timeout per run in seconds (default: 1800)")
    ap.add_argument("--workers", type=int, default=2, help="number of parallel workers (default: 2)")
    ap.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS, help="seeds list")
    ap.add_argument("--generators", nargs="+", default=["original", "full_negation"], help="generators to test")
    ap.add_argument("--arms", nargs="+", default=["static_100", "stall_relax_K5"], help="ratio arms (default: 2x2 design)")
    ap.add_argument("--output-file", default=OUTPUT_FILE, help="output JSON file")
    a = ap.parse_args()

    gens = {k: GENERATORS[k] for k in a.generators}
    arms = {k: RATIO_ARMS[k] for k in a.arms}
    out_file = a.output_file

    existing = load_json(out_file)
    commit = git_commit()

    jobs = [
        {"key": (gen_name, arm_name, seed), "generator": gen_name, "arm": arm_name, "seed": seed}
        for seed in a.seeds for arm_name in arms for gen_name in gens
    ]

    print(f"Candidate Generator Factorial on {PROBLEM} ({len(gens)}x{len(arms)} design, maxGen={a.max_gen}, workers={a.workers}): {len(jobs)} total runs.")

    def run_fn(j):
        extra_flags = gens[j["generator"]] + arms[j["arm"]]
        return run_one(
            PROBLEM,
            j["arm"],
            extra_flags,
            j["seed"],
            a.max_gen,
            a.timeout,
            breakout_fn=lambda raw: raw >= -2.0,
            extra={"generator": j["generator"]},
            commit=commit,
        )

    run_campaign(jobs, run_fn, out_file, existing, workers=a.workers)


if __name__ == "__main__":
    main()
