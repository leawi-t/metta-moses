import os
import sys
import re
import json
import time
import subprocess
import concurrent.futures
from collections import defaultdict
import numpy as np

REPO_DIR = "/home/nonplds/projects/metta-projects/metta-moses-representation"
PETTA_RUNNER = "/home/nonplds/projects/metta-projects/PeTTa/run.sh"

ARMS = {
    "new_sym_1x": {
        "permPolarityMode": "symmetric",
        "logicalPermRatio": 1.0,
        "hcMaxDistBoolean": 1
    },
    "new_sym_2x": {
        "permPolarityMode": "symmetric",
        "logicalPermRatio": 2.0,
        "hcMaxDistBoolean": 1
    },
    "new_sym_4x": {
        "permPolarityMode": "symmetric",
        "logicalPermRatio": 4.0,
        "hcMaxDistBoolean": 1
    }
}

SEEDS = [7, 11, 21, 29, 42]

def run_single(arm_name, seed, max_gen=15, problem="parity4"):
    cfg = ARMS[arm_name]
    cmd = [
        "bash",
        PETTA_RUNNER,
        "moses.metta",
        "-s",
        f"--problem={problem}",
        f"--maxGen={max_gen}",
        "--complexityRatio=3.5",
        "--maxRevisits=1",
        f"--seed={seed}",
        f"--permPolarityMode={cfg['permPolarityMode']}",
        f"--logicalPermRatio={cfg['logicalPermRatio']}",
        f"--hcMaxDistBoolean={cfg['hcMaxDistBoolean']}"
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
        elapsed = time.time() - t0
        output = proc.stdout
        
        # Parse Step2-Summary
        summary_m = re.search(
            r"\(Step2-Summary UniqueVisited:\s*(\d+)\s*TotalExpansions:\s*(\d+)\s*FallbackCount:\s*(\d+)\s*BestRaw:\s*([-+]?\d*\.?\d+)\s*BetterRawWorsePen:\s*(\d+)\s*(?:DistinctCulledBetterRaw:\s*(\d+)\s*)?Culled:\s*(\d+)\s*Levels:\s*\[(.*?)\]\)",
            output
        )
        
        best_raw = -1e9
        best_pen = -1e9
        literals = 0
        unique_visited = 0
        total_expansions = 0
        
        if summary_m:
            unique_visited = int(summary_m.group(1))
            total_expansions = int(summary_m.group(2))
            best_raw = float(summary_m.group(4))
        else:
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
            })
            
        if gen_stats:
            last = gen_stats[-1]
            best_pen = last["best_pen"]
            literals = last["literals"]
            
        print(f"[{problem} | {arm_name} | Seed {seed:2d}] Done in {elapsed:4.1f}s -> BestRaw: {best_raw:4.1f} | BestPen: {best_pen:6.2f} | Literals: {literals:2d}", flush=True)
        return {
            "problem": problem,
            "arm": arm_name,
            "seed": seed,
            "best_raw": best_raw,
            "best_pen": best_pen,
            "literals": literals,
            "unique_visited": unique_visited,
            "total_expansions": total_expansions,
            "elapsed": elapsed,
            "gen_stats": gen_stats
        }
    except Exception as e:
        print(f"[{problem} | {arm_name} | Seed {seed}] ERROR: {e}", flush=True)
        return None

def main():
    problem = sys.argv[1] if len(sys.argv) > 1 else "parity4"
    print("=" * 80)
    print(f"STARTING NEW SYMMETRIC GENERATOR SWEEP ON {problem.upper()}")
    print(f"Arms: {list(ARMS.keys())}")
    print(f"Seeds: {SEEDS} (maxGen=15, 2 parallel workers)")
    print("=" * 80, flush=True)
    
    tasks = []
    for arm_name in ARMS:
        for seed in SEEDS:
            tasks.append((arm_name, seed))
            
    results = []
    # Use max_workers=2 for WSL memory stability
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_to_task = {executor.submit(run_single, arm, seed, 15, problem): (arm, seed) for arm, seed in tasks}
        for future in concurrent.futures.as_completed(future_to_task):
            res = future.result()
            if res:
                results.append(res)
                
    # Aggregate results by arm
    by_arm = defaultdict(list)
    for r in results:
        by_arm[r["arm"]].append(r)
        
    summary = {}
    for arm_name, rows in by_arm.items():
        raws = [r["best_raw"] for r in rows]
        pens = [r["best_pen"] for r in rows if r["best_pen"] > -1e8]
        lits = [r["literals"] for r in rows]
        times = [r["elapsed"] for r in rows]
        
        summary[arm_name] = {
            "n": len(rows),
            "mean_raw": float(np.mean(raws)),
            "std_raw": float(np.std(raws)),
            "min_raw": float(np.min(raws)),
            "max_raw": float(np.max(raws)),
            "mean_pen": float(np.mean(pens)) if pens else -999.0,
            "mean_literals": float(np.mean(lits)),
            "mean_time": float(np.mean(times)),
            "perfect_solves": sum(1 for r in raws if r == 0.0),
            "raw_distribution": {str(k): raws.count(k) for k in sorted(set(raws))}
        }
        
    out_file = os.path.join(REPO_DIR, f"new_symmetric_results_{problem}.json")
    with open(out_file, "w") as f:
        json.dump({"summary": summary, "runs": results}, f, indent=2)
        
    print("\n" + "=" * 90)
    print(f"NEW SYMMETRIC SWEEP SUMMARY ON {problem.upper()} (Equal Evals across Arms)")
    print("=" * 90)
    header = f"{'Arm':<18} | {'N':<3} | {'Mean Raw':<10} | {'Max Raw':<8} | {'Mean Pen':<10} | {'Literals':<9} | {'Solves (Raw 0)':<14} | {'Mean Time':<9}"
    print(header)
    print("-" * len(header))
    
    for arm_name in ARMS:
        if arm_name in summary:
            s = summary[arm_name]
            print(f"{arm_name:<18} | {s['n']:<3} | {s['mean_raw']:6.2f}±{s['std_raw']:4.2f} | {s['max_raw']:8.1f} | {s['mean_pen']:10.2f} | {s['mean_literals']:9.1f} | {s['perfect_solves']:<14} | {s['mean_time']:6.1f}s")
            
    print("=" * 90)
    print(f"Detailed output saved to {out_file}")

if __name__ == "__main__":
    main()
