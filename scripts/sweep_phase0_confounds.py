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

COMPLEXITY_RATIOS = [3.5, 7.0, 14.0, 1000.0]
HC_THRESHOLDS = [0.5, 0.1, 0.0]

SEEDS_PARITY = [7, 11, 21, 29, 42]
SEEDS_MAJ7 = [7, 11, 21]

def run_single_instance(problem, seed, cr, thresh, max_gen):
    cmd = [
        "bash",
        PETTA_RUNNER,
        "moses.metta",
        "-s",
        f"--maxGen={max_gen}",
        f"--complexityRatio={cr}",
        f"--hcScoreImprovedThreshold={thresh}",
        "--maxRevisits=1",
        f"--seed={seed}"
    ]
    if problem == "majority7":
        cmd.extend(["--inputFile=majority7.csv", "--targetFeature=Out"])
    else:
        cmd.append(f"--problem={problem}")
        
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        elapsed = time.time() - t0
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
            
        solved = (best_raw == 0.0)
        ceiling_broken = False
        if problem == "parity4":
            ceiling_broken = (best_raw >= -2.0)
        elif problem == "parity5":
            ceiling_broken = (best_raw > -15.0)
            
        return {
            "problem": problem,
            "seed": seed,
            "complexityRatio": cr,
            "hcScoreImprovedThreshold": thresh,
            "max_gen": max_gen,
            "best_raw": best_raw,
            "best_pen": best_pen,
            "literals": literals,
            "expansions": expansions,
            "unique_visited": unique_visited,
            "solved": solved,
            "ceiling_broken": ceiling_broken,
            "elapsed": elapsed,
            "status": "ok"
        }
    except Exception as e:
        return {
            "problem": problem,
            "seed": seed,
            "complexityRatio": cr,
            "hcScoreImprovedThreshold": thresh,
            "max_gen": max_gen,
            "best_raw": -1e9,
            "status": f"error: {str(e)}"
        }

def run_phase0_sweep():
    output_file = os.path.join(REPO_DIR, "phase0_confound_sweep.json")
    all_results = []
    
    tasks = []
    # 1. parity4: 12 conditions x 5 seeds
    for cr in COMPLEXITY_RATIOS:
        for thresh in HC_THRESHOLDS:
            for s in SEEDS_PARITY:
                tasks.append(("parity4", s, cr, thresh, 15))
                
    # 2. parity5: 12 conditions x 5 seeds
    for cr in COMPLEXITY_RATIOS:
        for thresh in HC_THRESHOLDS:
            for s in SEEDS_PARITY:
                tasks.append(("parity5", s, cr, thresh, 10))
                
    # 3. majority7: 12 conditions x 3 seeds
    for cr in COMPLEXITY_RATIOS:
        for thresh in HC_THRESHOLDS:
            for s in SEEDS_MAJ7:
                tasks.append(("majority7", s, cr, thresh, 5))

    print(f"Total Phase 0 tasks scheduled: {len(tasks)}")
    
    # Run with 2 workers to respect memory/CPU limits
    completed = 0
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(run_single_instance, prob, s, cr, th, mg): (prob, s, cr, th, mg)
            for (prob, s, cr, th, mg) in tasks
        }
        
        for future in as_completed(futures):
            res = future.result()
            all_results.append(res)
            completed += 1
            if res["status"] == "ok":
                print(f"[{completed:3d}/{len(tasks)}] {res['problem']:<10} cr={res['complexityRatio']:<6} th={res['hcScoreImprovedThreshold']:<4} s={res['seed']:<3} -> Raw={res['best_raw']:<5.1f} Pen={res['best_pen']:<6.1f} Lits={res['literals']:<2} Break={res['ceiling_broken']} ({res['elapsed']:.1f}s)")
            else:
                print(f"[{completed:3d}/{len(tasks)}] ERROR on {res}")
                
            # Incremental save
            if completed % 5 == 0 or completed == len(tasks):
                with open(output_file, "w") as f:
                    json.dump(all_results, f, indent=2)
                    
    print("\nPhase 0 Sweep Complete. Summarizing results...\n")
    summarize_sweep(all_results)

def summarize_sweep(results):
    by_prob_config = defaultdict(list)
    for r in results:
        if r["status"] == "ok":
            key = (r["problem"], r["complexityRatio"], r["hcScoreImprovedThreshold"])
            by_prob_config[key].append(r)
            
    print("=" * 105)
    print("PHASE 0 CONFOUND SWEEP SUMMARY: OBJECTIVE FUNCTION & THRESHOLD IMPACT")
    print("=" * 105)
    print(f"{'Problem':<12} {'Ratio':<8} {'Thresh':<8} {'N':<4} {'Mean Raw':<10} {'Median Raw':<12} {'Break Rate':<12} {'Solve Rate':<12} {'Mean Lits':<10}")
    print("-" * 105)
    
    for (prob, cr, th), rows in sorted(by_prob_config.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        raws = [x["best_raw"] for x in rows]
        breaks = [1 if x["ceiling_broken"] else 0 for x in rows]
        solves = [1 if x["solved"] else 0 for x in rows]
        lits = [x["literals"] for x in rows]
        
        mean_raw = np.mean(raws)
        med_raw = np.median(raws)
        break_rate = np.mean(breaks)
        solve_rate = np.mean(solves)
        mean_lits = np.mean(lits)
        
        cr_label = "1000 (large)" if cr >= 1000 else str(cr)
        print(f"{prob:<12} {cr_label:<8} {th:<8} {len(rows):<4} {mean_raw:<10.2f} {med_raw:<12.1f} {break_rate*100:<11.1f}% {solve_rate*100:<11.1f}% {mean_lits:<10.1f}")
        
    print("=" * 105)

if __name__ == "__main__":
    run_phase0_sweep()
