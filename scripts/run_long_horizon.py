import os
import sys
import re
import json
import time
import argparse
import subprocess
import concurrent.futures
from collections import defaultdict
import numpy as np
import scipy.stats as stats

PETTA_RUNNER = "/home/nonplds/projects/metta-projects/PeTTa/run.sh"
REPO_DIR = "/home/nonplds/projects/metta-projects/metta-moses-representation"

ARMS = {
    "A_baseline": 999999,
    "B_visited": 1
}

def run_single_experiment(args):
    problem, arm_name, max_revisits, ratio, max_gen, seed = args
    cmd = [
        "bash",
        PETTA_RUNNER,
        "moses.metta",
        "-s",
        f"--problem={problem}",
        f"--maxGen={max_gen}",
        f"--complexityRatio={ratio}",
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
            timeout=600
        )
        elapsed = time.time() - t0
        output = proc.stdout
        
        # Parse Step2-Summary
        summary_m = re.search(
            r"\(Step2-Summary UniqueVisited:\s*(\d+)\s*TotalExpansions:\s*(\d+)\s*FallbackCount:\s*(\d+)\s*BestRaw:\s*([-+]?\d*\.?\d+)\s*BetterRawWorsePen:\s*(\d+)\s*(?:DistinctCulledBetterRaw:\s*(\d+)\s*)?Culled:\s*(\d+)\s*Levels:\s*\[(.*?)\]\)",
            output
        )
        
        distinct_culled = 0
        if summary_m:
            unique_visited = int(summary_m.group(1))
            total_expansions = int(summary_m.group(2))
            fallback_count = int(summary_m.group(3))
            best_raw = float(summary_m.group(4))
            better_raw_worse_pen = int(summary_m.group(5))
            distinct_culled = int(summary_m.group(6)) if summary_m.group(6) is not None else 0
            culled_count = int(summary_m.group(7))
            raw_levels_str = summary_m.group(8).strip()
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
            better_raw_worse_pen = 0
            culled_count = 0
            raw_levels = {}
            best_raw_m = re.findall(r"\(Step2-BestRaw Gen: \d+ Exp: \d+ Ever: ([-+]?\d*\.?\d+)", output)
            if best_raw_m:
                best_raw = float(best_raw_m[-1])
        
        # Parse per-generation Step2-GenStats
        gen_stats = []
        for gm in re.finditer(r"\(Step2-GenStats Gen:\s*(\d+)\s*Exp:\s*(\d+)\s*BestRaw:\s*([-+]?\d*\.?\d+)\s*Literals:\s*(\d+)\s*BestPen:\s*([-+]?\d*\.?\d+)\s*CulledThisGen:\s*(\d+)\s*DistinctCulledTotal:\s*(\d+)\)", output):
            gen_stats.append({
                "gen": int(gm.group(1)),
                "exp": int(gm.group(2)),
                "best_raw": float(gm.group(3)),
                "literals": int(gm.group(4)),
                "best_pen": float(gm.group(5)),
                "culled_this_gen": int(gm.group(6)),
                "distinct_culled_total": int(gm.group(7))
            })

        # Parse per-generation Step2-BestRaw progression (fallback/compat)
        progression = []
        for gm in re.finditer(r"\(Step2-BestRaw Gen:\s*(\d+)\s*Exp:\s*(\d+)\s*Ever:\s*([-+]?\d*\.?\d+)\s*CurrentMetapop:\s*([-+]?\d*\.?\d+)\)", output):
            progression.append({
                "gen": int(gm.group(1)),
                "exp": int(gm.group(2)),
                "ever": float(gm.group(3)),
                "cur": float(gm.group(4))
            })
            
        # Count repeated expansions from log lines
        repeated_m = re.findall(r"Repeated:\s*TRUE", output)
        repeated_expansions = len(repeated_m)
        
        # Calculate plateau length on RAW score vs PENALIZED score
        plateau_raw = 0
        plateau_pen = 0
        if gen_stats:
            final_raw = gen_stats[-1]["best_raw"]
            final_pen = gen_stats[-1]["best_pen"]
            for step in reversed(gen_stats):
                if step["best_raw"] == final_raw:
                    plateau_raw += 1
                else:
                    break
            for step in reversed(gen_stats):
                if step["best_pen"] == final_pen:
                    plateau_pen += 1
                else:
                    break
        elif progression:
            final_best = progression[-1]["ever"]
            for step in reversed(progression):
                if step["ever"] == final_best:
                    plateau_raw += 1
                else:
                    break

        return {
            "problem": problem,
            "arm": arm_name,
            "max_revisits": max_revisits,
            "ratio": ratio,
            "max_gen": max_gen,
            "seed": seed,
            "best_raw": best_raw,
            "unique_visited": unique_visited,
            "total_expansions": total_expansions,
            "repeated_expansions": repeated_expansions,
            "fallback_count": fallback_count,
            "better_raw_worse_pen": better_raw_worse_pen,
            "distinct_culled": distinct_culled,
            "culled_count": culled_count,
            "raw_levels": raw_levels,
            "plateau_raw": plateau_raw,
            "plateau_pen": plateau_pen,
            "plateau_len": plateau_raw,
            "gen_stats": gen_stats,
            "progression": progression,
            "duration": elapsed,
            "success": proc.returncode == 0
        }
    except Exception as e:
        return {
            "problem": problem,
            "arm": arm_name,
            "max_revisits": max_revisits,
            "ratio": ratio,
            "max_gen": max_gen,
            "seed": seed,
            "best_raw": -1e9,
            "error": str(e),
            "success": False,
            "duration": time.time() - t0
        }

def analyze_dataset(results, problems, ratios, num_seeds):
    print("\n" + "="*85)
    print("LONG-HORIZON RERUN ANALYSIS: BASELINE VS VISITED TRACKING")
    print("="*85)
    
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for r in results:
        if r.get("success"):
            data[r["problem"]][r["ratio"]][r["arm"]][r["seed"]] = r

    for problem in problems:
        for ratio in ratios:
            print(f"\n### Problem: {problem} | Ratio: {ratio} (N={num_seeds} paired seeds)")
            print("-" * 115)
            print(f"{'Arm':<15} {'Mean Raw':<10} {'Median':<8} {'Duplicates':<12} {'Fallbacks':<10} {'Plat(Raw)':<11} {'Plat(Pen)':<11} {'DistinctCulled':<16} {'BetterRawWorsePen':<18}")
            print("-" * 115)
            
            arm_scores = {}
            arm_breakouts = {}
            for arm_name in ARMS:
                runs = [data[problem][ratio][arm_name][s] for s in range(1, num_seeds + 1) if s in data[problem][ratio][arm_name]]
                scores = [r["best_raw"] for r in runs]
                arm_scores[arm_name] = scores
                dups = [r.get("repeated_expansions", 0) for r in runs]
                fallbacks = [r.get("fallback_count", 0) for r in runs]
                plateaus_raw = [r.get("plateau_raw", r.get("plateau_len", 0)) for r in runs]
                plateaus_pen = [r.get("plateau_pen", r.get("plateau_len", 0)) for r in runs]
                distinct_culled = [r.get("distinct_culled", 0) for r in runs]
                better_raw = [r.get("better_raw_worse_pen", 0) for r in runs]
                
                mean_s = np.mean(scores) if scores else 0
                med_s = np.median(scores) if scores else 0
                mean_dup = np.mean(dups) if dups else 0
                mean_fb = np.mean(fallbacks) if fallbacks else 0
                mean_plat_raw = np.mean(plateaus_raw) if plateaus_raw else 0
                mean_plat_pen = np.mean(plateaus_pen) if plateaus_pen else 0
                mean_dist_culled = np.mean(distinct_culled) if distinct_culled else 0
                mean_brwp = np.mean(better_raw) if better_raw else 0
                
                print(f"{arm_name:<15} {mean_s:<10.3f} {med_s:<8.1f} {mean_dup:<12.2f} {mean_fb:<10.2f} {mean_plat_raw:<11.1f} {mean_plat_pen:<11.1f} {mean_dist_culled:<16.1f} {mean_brwp:<18.1f}")
            
            # Statistical Tests: Paired Wilcoxon and McNemar
            s_base = arm_scores.get("A_baseline", [])
            s_vis = arm_scores.get("B_visited", [])
            if len(s_base) == len(s_vis) and len(s_base) > 0:
                diffs = [v - b for v, b in zip(s_vis, s_base)]
                non_zero = [d for d in diffs if d != 0]
                print("\n  [Wilcoxon Signed-Rank Test (Raw Score Delta)]:")
                if non_zero:
                    stat, pval = stats.wilcoxon(s_vis, s_base)
                    wins = sum(d > 0 for d in diffs)
                    losses = sum(d < 0 for d in diffs)
                    ties = sum(d == 0 for d in diffs)
                    print(f"    Visited vs Baseline: W={stat:.1f}, p={pval:.4e} (Visited wins: {wins}, Baseline wins: {losses}, Ties: {ties})")
                else:
                    print("    Visited vs Baseline: all paired score differences are 0")

                # McNemar Breakout Test
                # Define breakout threshold per problem
                threshold = -7.0 if problem == "parity4" else (-1.0 if problem == "majority5" else 0.0)
                base_break = [s >= threshold for s in s_base]
                vis_break = [s >= threshold for s in s_vis]
                
                n00 = sum(not b and not v for b, v in zip(base_break, vis_break))
                n11 = sum(b and v for b, v in zip(base_break, vis_break))
                n01 = sum(not b and v for b, v in zip(base_break, vis_break)) # baseline failed, visited broke out
                n10 = sum(b and not v for b, v in zip(base_break, vis_break)) # baseline broke out, visited failed
                
                print(f"\n  [McNemar Test for Breakout Rate >= {threshold}]:")
                print(f"    Baseline Breakout Rate: {sum(base_break)}/{len(base_break)} ({sum(base_break)/len(base_break)*100:.1f}%)")
                print(f"    Visited Breakout Rate:  {sum(vis_break)}/{len(vis_break)} ({sum(vis_break)/len(vis_break)*100:.1f}%)")
                print(f"    Contingency table: Both broke out={n11}, Both failed={n00}, Visited-only={n01}, Baseline-only={n10}")
                
                discordant = n01 + n10
                if discordant > 0:
                    bt = stats.binomtest(n01, discordant, 0.5)
                    print(f"    McNemar Exact Binomial p-value: {bt.pvalue:.4e} (two-sided)")
                else:
                    print("    No discordant pairs (exact agreement).")

            # Per-Seed Detailed Table for each Arm
            for arm_name in sorted(data[problem][ratio].keys()):
                runs = [data[problem][ratio][arm_name][s] for s in range(1, num_seeds + 1) if s in data[problem][ratio][arm_name]]
                if not runs:
                    continue
                print(f"\n  [Per-Seed Detailed Breakdown for {arm_name}]:")
                print(f"  {'Seed':<6} {'Final Raw':<10} {'Literals':<9} {'Plat(Raw)':<10} {'Plat(Pen)':<10} {'Stall Onset':<12} {'Culled@Onset':<13} {'Culled@End':<11} {'Growth':<8}")
                print("  " + "-" * 95)
                for r in runs:
                    s = r["seed"]
                    raw = r["best_raw"]
                    p_raw = r.get("plateau_raw", r.get("plateau_len", 0))
                    p_pen = r.get("plateau_pen", r.get("plateau_len", 0))
                    gen_stats = r.get("gen_stats", [])
                    if gen_stats:
                        final_lits = gen_stats[-1]["literals"]
                        final_raw_val = gen_stats[-1]["best_raw"]
                        onset_step = next((st for st in gen_stats if st["best_raw"] == final_raw_val), gen_stats[-1])
                        onset_gen = onset_step["gen"]
                        culled_onset = onset_step["distinct_culled_total"]
                        culled_end = gen_stats[-1]["distinct_culled_total"]
                    else:
                        final_lits = "N/A"
                        onset_gen = "N/A"
                        culled_onset = "N/A"
                        culled_end = r.get("distinct_culled", 0)
                    growth = (culled_end - culled_onset) if isinstance(culled_end, int) and isinstance(culled_onset, int) else "N/A"
                    print(f"  {s:<6} {raw:<10.1f} {str(final_lits):<9} {p_raw:<10} {p_pen:<10} {str(onset_gen):<12} {str(culled_onset):<13} {str(culled_end):<11} {str(growth):<8}")

            # Mean Expansion Index to Reach Each Milestone
            print("\n  Mean Expansion Index to Reach Each Milestone:")
            all_levels = set()
            for arm_name in ARMS:
                for s in range(1, num_seeds + 1):
                    if s in data[problem][ratio][arm_name]:
                        for k in data[problem][ratio][arm_name][s].get("raw_levels", {}).keys():
                            try:
                                all_levels.add(float(k))
                            except ValueError:
                                pass
            
            sorted_levels = sorted(all_levels)
            if sorted_levels:
                header = f"    {'Arm':<15}" + "".join(f"{f'Score {lvl}':<14}" for lvl in sorted_levels)
                print(header)
                for arm_name in ARMS:
                    row = f"    {arm_name:<15}"
                    for lvl in sorted_levels:
                        reach_times = []
                        for s in range(1, num_seeds + 1):
                            if s in data[problem][ratio][arm_name]:
                                rl = data[problem][ratio][arm_name][s].get("raw_levels", {})
                                for k, v in rl.items():
                                    try:
                                        if float(k) == lvl:
                                            reach_times.append(v)
                                            break
                                    except ValueError:
                                        pass
                        if reach_times:
                            row += f"{np.mean(reach_times):<7.2f} (n={len(reach_times):<2})  "
                        else:
                            row += f"{'N/A':<14}"
                    print(row)
            print("-" * 115)

def main():
    parser = argparse.ArgumentParser(description="Run long-horizon sweep for MOSES visited tracking.")
    parser.add_argument("--problems", nargs="+", default=["parity4", "parity3"], help="Problems to run")
    parser.add_argument("--ratios", nargs="+", type=float, default=[3.5, 10.0], help="Complexity ratios")
    parser.add_argument("--arms", nargs="+", default=["A_baseline", "B_visited"], help="Arms to run")
    parser.add_argument("--maxGen", type=int, default=30, help="Maximum generations")
    parser.add_argument("--seeds", type=int, default=30, help="Number of seeds")
    parser.add_argument("--workers", type=int, default=3, help="Parallel worker count")
    parser.add_argument("--output", default="long_horizon_results.json", help="Output JSON file")
    args = parser.parse_args()

    selected_arms = {k: v for k, v in ARMS.items() if k in args.arms}
    tasks = []
    for problem in args.problems:
        for ratio in args.ratios:
            for arm_name, max_revisits in selected_arms.items():
                for seed in range(1, args.seeds + 1):
                    tasks.append((problem, arm_name, max_revisits, ratio, args.maxGen, seed))

    print(f"Starting long-horizon sweep: {len(tasks)} tasks.")
    print(f"Problems: {args.problems} | Ratios: {args.ratios} | Arms: {list(selected_arms.keys())} | maxGen: {args.maxGen} | Seeds: 1..{args.seeds}")
    
    out_path = os.path.join(REPO_DIR, args.output)
    existing_results = []
    completed_keys = set()
    if os.path.exists(out_path):
        try:
            with open(out_path, "r") as f:
                existing_results = json.load(f)
            for r in existing_results:
                if r.get("success"):
                    completed_keys.add((r["problem"], r["arm"], r["ratio"], r["seed"]))
            print(f"Loaded {len(completed_keys)} already completed runs from {out_path}", flush=True)
        except Exception:
            existing_results = []

    remaining_tasks = [
        t for t in tasks 
        if (t[0], t[1], t[3], t[5]) not in completed_keys
    ]

    print(f"Tasks to run: {len(remaining_tasks)} (skipping {len(completed_keys)} already done)", flush=True)
    results = list(existing_results)

    if remaining_tasks:
        start_time = time.time()
        completed = 0
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(run_single_experiment, t): t for t in remaining_tasks}
            for f in concurrent.futures.as_completed(futures):
                try:
                    res = f.result()
                except Exception as ex:
                    task_info = futures[f]
                    res = {
                        "problem": task_info[0],
                        "arm": task_info[1],
                        "max_revisits": task_info[2],
                        "ratio": task_info[3],
                        "max_gen": task_info[4],
                        "seed": task_info[5],
                        "best_raw": -1e9,
                        "error": str(ex),
                        "success": False
                    }
                results.append(res)
                completed += 1
                
                # Checkpoint immediately to disk
                with open(out_path, "w") as out_f:
                    json.dump(results, out_f, indent=2)

                print(f"Progress: {completed}/{len(remaining_tasks)} completed | Latest: {res['problem']} {res['arm']} r={res['ratio']} s={res['seed']} -> raw={res['best_raw']} ({time.time() - start_time:.1f}s)", flush=True)

        print(f"\nAll runs completed! Total time: {time.time() - start_time:.1f}s.", flush=True)
    else:
        print("All requested tasks are already completed!", flush=True)

    analyze_dataset(results, args.problems, args.ratios, args.seeds)

if __name__ == "__main__":
    main()
