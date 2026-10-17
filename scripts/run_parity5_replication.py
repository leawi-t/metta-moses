#!/usr/bin/env python3
"""Step 2: parity5 fresh-seed replication (seeds 21-60).

Fixes: maxGen is taken from the original parity5 sweep (the old hard-coded 10 may not match it) and
the script refuses to run if it cannot be confirmed; adds trigger_only_K5, a control whose trigger
schedule matches K5 (the original control used K=3, so K5-vs-control was confounded); seed-major
scheduling; timeouts keep partial output; keys no longer collide.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moses_runner_common import (REPO_DIR, git_commit, infer_max_gen, load_json, run_campaign,  # noqa: E402
                                 run_one)

OUTPUT_FILE = os.path.join(REPO_DIR, "parity5_replication_results.json")
K5 = ["--stallThresholdK=5", "--relaxWindowMinM=3", "--relaxGraceG=2", "--relaxCooldownC=3"]
K3 = ["--stallThresholdK=3", "--relaxWindowMinM=3", "--relaxGraceG=2", "--relaxCooldownC=3"]
ARMS = {
    "static_14": ["--complexityRatio=14.0", "--stallRelaxationMode=False"],
    "static_100": ["--complexityRatio=100.0", "--stallRelaxationMode=False"],
    "stall_relax_K5": ["--stallRelaxationMode=dynamic", "--baseComplexityRatio=14.0",
                       "--relaxedComplexityRatio=100.0"] + K5,
    "trigger_only_K5": ["--stallRelaxationMode=trigger_only", "--baseComplexityRatio=14.0",
                        "--relaxedComplexityRatio=14.0"] + K5,
    "trigger_only_ctrl": ["--stallRelaxationMode=trigger_only", "--baseComplexityRatio=14.0",
                          "--relaxedComplexityRatio=14.0"] + K3,
}
SEEDS = list(range(21, 61))
PROBLEM = "parity5"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-gen", type=int, default=None)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seeds", type=int, nargs="+", default=None, help="override seed list (e.g. for dry runs)")
    ap.add_argument("--output-file", default=OUTPUT_FILE, help="override output JSON file")
    a = ap.parse_args()

    seeds = a.seeds if a.seeds is not None else SEEDS
    out_file = a.output_file

    inferred = infer_max_gen(PROBLEM)
    max_gen = a.max_gen or inferred
    if max_gen is None:
        sys.exit("Cannot confirm the original parity5 maxGen; pass --max-gen explicitly.")
    if inferred is not None and max_gen != inferred:
        print(f"WARNING: --max-gen={max_gen} differs from the original sweep ({inferred}); "
              f"results will not be protocol-matched to seeds 1-20.")
    print(f"parity5 maxGen={max_gen}")

    commit = git_commit()
    jobs = [{"key": (arm, seed, 1), "arm": arm, "seed": seed} for seed in seeds for arm in ARMS]

    def run_fn(j):
        return run_one(PROBLEM, j["arm"], ARMS[j["arm"]], j["seed"], max_gen, a.timeout,
                       breakout_fn=lambda raw: raw > -15.0, commit=commit)

    run_campaign(jobs, run_fn, out_file, load_json(out_file), workers=a.workers)



if __name__ == "__main__":
    main()