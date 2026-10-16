import os
import sys
import subprocess
import re
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import numpy as np

REPO_DIR = "/home/nonplds/projects/metta-projects/metta-moses-representation"
PETTA_RUNNER = "/home/nonplds/projects/metta-projects/PeTTa/run.sh"

RATIOS = [14.0, 20.0, 50.0, 100.0, 300.0, 1000.0]
SEEDS = list(range(1, 21)) # 20 paired seeds
PROBLEMS = ["parity4", "majority5", "parity5"]

def run_single(problem, seed, ratio, max_gen=15):
    cmd = [
        "bash",
        PETTA_RUNNER,
        "moses.metta",
        "-s",
        f"--problem={problem}",
        f"--maxGen={max_gen}",
        f"--complexityRatio={ratio}",
        "--hcScoreImprovedThreshold=0.5",
        "--maxRevisits=1",
        f"--seed={seed}"
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        wall_time = time.time() - t0
        out = proc.stdout
        
        # Parse Step2-Summary
        m_sum = re.search(
            r"\(Step2-Summary UniqueVisited:\s*(\d+)\s*TotalExpansions:\s*(\d+)\s*FallbackCount:\s*(\d+)\s*BestRaw:\s*([-+]?\d*\.?\d+)\s*BetterRawWorsePen:\s*(\d+)\s*(?:DistinctCulledBetterRaw:\s*(\d+)\s*)?Culled:\s*(\d+)\s*Levels:\s*\[(.*?)\]\)",
            out
        )
        
        best_raw = -1e9
        best_pen = -1e9
        literals = 0
        expansions = 0
        unique_visited = 0
        
        if m_sum:
            unique_visited = int(m_sum.group(1))
            expansions = int(m_sum.group(2))
            best_raw = float(m_sum.group(4))
        else:
            m_raw = re.findall(r"\(Step2-BestRaw Gen: \d+ Exp: \d+ Ever: ([-+]?\d*\.?\d+)", out)
            if m_raw:
                best_raw = float(m_raw[-1])
                
        # Parse last Step2-GenStats for literals and bestPen
        m_gen = re.findall(
            r"\(Step2-GenStats Gen: \d+ Exp: \d+ BestRaw: ([-+]?\d*\.?\d+) Literals: (\d+) BestPen: ([-+]?\d*\.?\d+)",
            out
        )
        if m_gen:
            best_pen = float(m_gen[-1][2])
            literals = int(m_gen[-1][1])
            
        # Parse total evaluations (sum of OptimizedDeme across demes)
        evals_matches = re.findall(r"\(OptimizedDeme:\s*(\d+)\)", out)
        total_evals = sum(int(x) for x in evals_matches) if evals_matches else 0
        
        # Breakout definition:
        # parity4: raw >= -2.0
        # majority5: raw >= -1.0
        # parity5: raw > -15.0
        solved = (best_raw == 0.0)
        breakout = False
        if problem == "parity4":
            breakout = (best_raw >= -2.0)
        elif problem == "majority5":
            breakout = (best_raw >= -1.0)
        elif problem == "parity5":
            breakout = (best_raw > -15.0)
            
        return {
            "problem": problem,
            "seed": seed,
            "ratio": ratio,
            "max_gen": max_gen,
            "best_raw": best_raw,
            "best_pen": best_pen,
            "literals": literals,
            "total_evals": total_evals,
            "wall_time": wall_time,
            "expansions": expansions,
            "unique_visited": unique_visited,
            "solved": solved,
            "breakout": breakout,
            "status": "ok"
        }
    except Exception as e:
        return {
            "problem": problem,
            "seed": seed,
            "ratio": ratio,
            "max_gen": max_gen,
            "best_raw": -1e9,
            "status": f"error: {str(e)}"
        }

def run_dense_sweep():
    output_file = os.path.join(REPO_DIR, "dense_ratio_sweep_results.json")
    all_results = []
    completed_keys = set()
    
    if os.path.exists(output_file):
        try:
            with open(output_file) as f:
                all_results = json.load(f)
            for r in all_results:
                if r.get("status") == "ok":
                    completed_keys.add((r["problem"], float(r["ratio"]), int(r["seed"])))
            print(f"Loaded {len(all_results)} existing runs ({len(completed_keys)} unique completed). Resuming...", flush=True)
        except Exception as e:
            print(f"Warning: could not read {output_file}: {e}", flush=True)
            
    tasks = []
    for prob in PROBLEMS:
        mg = 15 if prob in ("parity4", "majority5") else 10
        for r in RATIOS:
            for s in SEEDS:
                if (prob, float(r), int(s)) not in completed_keys:
                    tasks.append((prob, s, r, mg))
                
    total_total = len(PROBLEMS) * len(RATIOS) * len(SEEDS)
    print(f"Total tasks: {total_total} | Already completed: {len(completed_keys)} | Remaining to run: {len(tasks)}", flush=True)
    print(f"Problems: {PROBLEMS}", flush=True)
    print(f"Ratios: {RATIOS}", flush=True)
    print(f"Seeds: {len(SEEDS)} (1 to 20)", flush=True)
    
    if not tasks:
        print("All tasks already completed! Summarizing...", flush=True)
        summarize_dense_sweep(all_results)
        return
        
    completed = len(completed_keys)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(run_single, prob, s, r, mg): (prob, s, r, mg)
            for (prob, s, r, mg) in tasks
        }
        
        for future in as_completed(futures):
            res = future.result()
            all_results.append(res)
            completed += 1
            if res["status"] == "ok":
                print(f"[{completed:3d}/{total_total}] {res['problem']:<10} r={res['ratio']:<6} s={res['seed']:<2} -> Raw={res['best_raw']:<5.1f} Lits={res['literals']:<2} Evals={res['total_evals']:<5} Break={res['breakout']} ({res['wall_time']:.1f}s)", flush=True)
            else:
                print(f"[{completed:3d}/{total_total}] ERROR: {res}", flush=True)
                
            if completed % 5 == 0 or completed == total_total:
                with open(output_file, "w") as f:
                    json.dump(all_results, f, indent=2)
                    
    print("\nDense Sweep Complete. Generating Summary...\n")
    summarize_dense_sweep(all_results)

def summarize_dense_sweep(results):
    by_prob_ratio = defaultdict(list)
    for r in results:
        if r["status"] == "ok":
            key = (r["problem"], r["ratio"])
            by_prob_ratio[key].append(r)
            
    print("=" * 115)
    print("DENSE RATIO SWEEP: FINDING MINIMUM EFFECTIVE RATIO AND BLOAT THRESHOLD")
    print("=" * 115)
    print(f"{'Problem':<12} {'Ratio':<8} {'N':<4} {'Mean Raw':<10} {'Median Raw':<12} {'Break Rate':<12} {'Solve Rate':<12} {'Mean Lits':<11} {'Mean Evals':<12} {'Mean Time (s)':<12}")
    print("-" * 115)
    
    for (prob, r), rows in sorted(by_prob_ratio.items(), key=lambda x: (x[0][0], x[0][1])):
        raws = [x["best_raw"] for x in rows]
        breaks = [1 if x["breakout"] else 0 for x in rows]
        solves = [1 if x["solved"] else 0 for x in rows]
        lits = [x["literals"] for x in rows]
        evals = [x["total_evals"] for x in rows]
        times = [x["wall_time"] for x in rows]
        
        mean_raw = np.mean(raws)
        med_raw = np.median(raws)
        break_rate = np.mean(breaks)
        solve_rate = np.mean(solves)
        mean_lits = np.mean(lits)
        mean_evals = np.mean(evals)
        mean_time = np.mean(times)
        
        print(f"{prob:<12} {r:<8.1f} {len(rows):<4} {mean_raw:<10.2f} {med_raw:<12.1f} {break_rate*100:<11.1f}% {solve_rate*100:<11.1f}% {mean_lits:<11.1f} {mean_evals:<12.1f} {mean_time:<12.2f}")
        
    print("=" * 115)

if __name__ == "__main__":
    run_dense_sweep()
