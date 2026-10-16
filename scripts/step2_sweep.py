import os
import sys
import re
import json
import time
import subprocess
import concurrent.futures
from collections import defaultdict
import numpy as np
import scipy.stats as stats

PROBLEMS = ["parity4", "majority5", "majority3"]
ARMS = {
    "A_baseline": 999999,
    "B_maxRev1": 1,
    "C_maxRev2": 2
}
NUM_SEEDS = 30
SEEDS = list(range(1, NUM_SEEDS + 1))
RATIO = 3.5
MAX_GEN = 5
PETTA_RUNNER = "/home/nonplds/projects/metta-projects/PeTTa/run.sh"
REPO_DIR = "/home/nonplds/projects/metta-projects/metta-moses-representation"

def run_single_experiment(args):
    problem, arm_name, max_revisits, seed = args
    cmd = [
        "bash",
        PETTA_RUNNER,
        "moses.metta",
        "-s",
        f"--problem={problem}",
        f"--maxGen={MAX_GEN}",
        f"--complexityRatio={RATIO}",
        f"--maxRevisits={max_revisits}",
        f"--seed={seed}"
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180
        )
        elapsed = time.time() - t0
        output = proc.stdout
        
        # Parse Step2-Summary
        summary_m = re.search(
            r"\(Step2-Summary UniqueVisited:\s*(\d+)\s*TotalExpansions:\s*(\d+)\s*FallbackCount:\s*(\d+)\s*BestRaw:\s*([-+]?\d*\.?\d+)\s*Levels:\s*\[(.*?)\]\)",
            output
        )
        
        if summary_m:
            unique_visited = int(summary_m.group(1))
            total_expansions = int(summary_m.group(2))
            fallback_count = int(summary_m.group(3))
            best_raw = float(summary_m.group(4))
            raw_levels_str = summary_m.group(5).strip()
            raw_levels = {}
            if raw_levels_str:
                for pair in raw_levels_str.split():
                    if ":" in pair:
                        k, v = pair.split(":")
                        try:
                            raw_levels[float(k)] = int(v)
                        except ValueError:
                            pass
        else:
            # Fallback parsing
            best_raw = -1e9
            unique_visited = 0
            total_expansions = 0
            fallback_count = 0
            raw_levels = {}
            best_raw_m = re.findall(r"\(Step2-BestRaw Gen: \d+ Exp: \d+ Ever: ([-+]?\d*\.?\d+)", output)
            if best_raw_m:
                best_raw = float(best_raw_m[-1])
        
        # Count repeated expansions from log lines
        repeated_m = re.findall(r"Repeated:\s*TRUE", output)
        repeated_expansions = len(repeated_m)

        return {
            "problem": problem,
            "arm": arm_name,
            "max_revisits": max_revisits,
            "seed": seed,
            "best_raw": best_raw,
            "unique_visited": unique_visited,
            "total_expansions": total_expansions,
            "repeated_expansions": repeated_expansions,
            "fallback_count": fallback_count,
            "raw_levels": raw_levels,
            "duration": elapsed,
            "success": proc.returncode == 0
        }
    except Exception as e:
        return {
            "problem": problem,
            "arm": arm_name,
            "max_revisits": max_revisits,
            "seed": seed,
            "best_raw": -1e9,
            "error": str(e),
            "success": False,
            "duration": time.time() - t0
        }

def run_sweep():
    tasks = []
    for problem in PROBLEMS:
        for arm_name, max_revisits in ARMS.items():
            for seed in SEEDS:
                tasks.append((problem, arm_name, max_revisits, seed))

    print(f"Starting sweep: {len(tasks)} total runs across {len(PROBLEMS)} problems, {len(ARMS)} arms, {NUM_SEEDS} seeds.")
    results = []
    
    # Run with 8 workers
    num_workers = min(8, os.cpu_count() or 4)
    start_time = time.time()
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(run_single_experiment, t): t for t in tasks}
        completed = 0
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            results.append(res)
            completed += 1
            if completed % 15 == 0 or completed == len(tasks):
                print(f"Progress: {completed}/{len(tasks)} runs completed ({time.time() - start_time:.1f}s)")

    total_time = time.time() - start_time
    print(f"\nSweep completed in {total_time:.2f} seconds.")
    
    # Save raw results
    output_file = os.path.join(REPO_DIR, "step2_sweep_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {output_file}")
    
    analyze_results(results)

def analyze_results(results):
    print("\n" + "="*80)
    print("STEP 2 BASELINE ANALYSIS & WILCOXON COMPARISON")
    print("="*80)
    
    # Group results by problem -> arm -> list of runs sorted by seed
    data = defaultdict(lambda: defaultdict(dict))
    for r in results:
        if r.get("success"):
            data[r["problem"]][r["arm"]][r["seed"]] = r

    for problem in PROBLEMS:
        print(f"\n### Problem: {problem} (N={NUM_SEEDS} paired seeds)")
        print("-" * 75)
        print(f"{'Arm':<15} {'Mean Raw':<12} {'Std':<8} {'Median':<8} {'Duplicates':<12} {'Fallbacks':<10} {'Expansions':<10}")
        print("-" * 75)
        
        arm_scores = {}
        for arm_name in ARMS:
            runs = [data[problem][arm_name][s] for s in SEEDS if s in data[problem][arm_name]]
            scores = [r["best_raw"] for r in runs]
            arm_scores[arm_name] = scores
            dups = [r.get("repeated_expansions", 0) for r in runs]
            fallbacks = [r.get("fallback_count", 0) for r in runs]
            exps = [r.get("total_expansions", 0) for r in runs]
            
            mean_s = np.mean(scores) if scores else 0
            std_s = np.std(scores) if scores else 0
            med_s = np.median(scores) if scores else 0
            mean_dup = np.mean(dups) if dups else 0
            mean_fb = np.mean(fallbacks) if fallbacks else 0
            mean_exp = np.mean(exps) if exps else 0
            
            print(f"{arm_name:<15} {mean_s:<12.3f} {std_s:<8.3f} {med_s:<8.1f} {mean_dup:<12.2f} {mean_fb:<10.2f} {mean_exp:<10.2f}")
        
        # Paired Wilcoxon Signed-Rank Tests
        print("\n  Pairwise Wilcoxon Signed-Rank Tests (Paired across identical seeds):")
        comparisons = [
            ("B_maxRev1", "A_baseline"),
            ("C_maxRev2", "A_baseline"),
            ("B_maxRev1", "C_maxRev2")
        ]
        
        for arm1, arm2 in comparisons:
            s1 = arm_scores.get(arm1, [])
            s2 = arm_scores.get(arm2, [])
            if len(s1) == len(s2) and len(s1) > 0:
                diffs = [x - y for x, y in zip(s1, s2)]
                non_zero_diffs = [d for d in diffs if d != 0]
                if len(non_zero_diffs) > 0:
                    try:
                        stat, pval = stats.wilcoxon(s1, s2)
                        print(f"    {arm1} vs {arm2}: stat={stat:.1f}, p={pval:.4e} (wins: {sum(d > 0 for d in diffs)}, losses: {sum(d < 0 for d in diffs)}, ties: {sum(d == 0 for d in diffs)})")
                    except Exception as e:
                        print(f"    {arm1} vs {arm2}: could not compute Wilcoxon ({e})")
                else:
                    print(f"    {arm1} vs {arm2}: identical distributions (all paired differences are zero)")
            else:
                print(f"    {arm1} vs {arm2}: unequal sample sizes")

        # Evaluations to reach each raw score level
        print("\n  Mean Evaluations to Reach Each Raw Level:")
        all_levels = set()
        for arm_name in ARMS:
            for s in SEEDS:
                if s in data[problem][arm_name]:
                    all_levels.update(data[problem][arm_name][s].get("raw_levels", {}).keys())
        
        sorted_levels = sorted(all_levels)
        if sorted_levels:
            header = f"    {'Arm':<15}" + "".join(f"{f'Score {lvl}':<12}" for lvl in sorted_levels)
            print(header)
            for arm_name in ARMS:
                row = f"    {arm_name:<15}"
                for lvl in sorted_levels:
                    reach_times = [
                        data[problem][arm_name][s]["raw_levels"][lvl]
                        for s in SEEDS
                        if s in data[problem][arm_name] and lvl in data[problem][arm_name][s].get("raw_levels", {})
                    ]
                    if reach_times:
                        row += f"{np.mean(reach_times):<12.2f} (n={len(reach_times)})"
                    else:
                        row += f"{'N/A':<12}"
                print(row)
        print("-" * 75)

if __name__ == "__main__":
    run_sweep()
