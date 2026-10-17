#!/usr/bin/env python3
"""
Step 1: Parity4 Budget Check Benchmark Runner.

Runs Parity4 with a 3x generation budget (MaxGen=45) under:
1. static_100
2. stall_relax_K5
Across 10 seeds (1-10).

Goal: Determine whether Parity4 stagnation (0/100 solves) is a budget limitation
or a structural fitness landscape barrier.
Saves progress atomically to budget_check_results.json.
"""

import os
import sys
import subprocess
import re
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_DIR = "/home/nonplds/projects/metta-projects/metta-moses-representation"
PETTA_RUNNER = "/home/nonplds/projects/metta-projects/PeTTa/run.sh"
OUTPUT_FILE = os.path.join(REPO_DIR, "budget_check_results.json")

ARMS = {
    "static_100": {
        "flags": ["--complexityRatio=100.0", "--stallRelaxationMode=False"],
        "desc": "Static relaxed upper bound 100.0"
    },
    "stall_relax_K5": {
        "flags": [
            "--stallRelaxationMode=dynamic",
            "--baseComplexityRatio=14.0",
            "--relaxedComplexityRatio=100.0",
            "--stallThresholdK=5",
            "--relaxWindowMinM=3",
            "--relaxGraceG=2",
            "--relaxCooldownC=3"
        ],
        "desc": "Stall-triggered relaxation (K=5, M=3, G=2, C=3)"
    }
}

SEEDS = list(range(1, 11)) # 10 seeds
MAX_GEN = 45 # 3x standard budget (15 -> 45)
BUDGET_MULT = 3

def parse_field(pattern, text, default=None, cast=int):
    m = re.search(pattern, text)
    if m:
        try:
            return cast(m.group(1))
        except Exception:
            pass
    return default

def run_single(arm_name, seed):
    arm_cfg = ARMS[arm_name]
    cmd = [
        "bash",
        PETTA_RUNNER,
        "moses.metta",
        "-s",
        "--problem=parity4",
        f"--maxGen={MAX_GEN}",
        "--hcScoreImprovedThreshold=0.5",
        "--maxRevisits=1",
        f"--seed={seed}"
    ] + arm_cfg["flags"]
    
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=900 # generous timeout for 3x budget
        )
        wall_time = time.time() - t0
        out = proc.stdout
        
        m_sum = re.search(r"\(Step2-Summary (.*?)\)", out)
        best_raw = -1e9
        best_pen = -1e9
        literals = 0
        expansions = 0
        unique_visited = 0
        relaxed_gens = 0
        fraction_relaxed = 0.0
        switch_count = 0
        
        if m_sum:
            s_text = m_sum.group(1)
            unique_visited = parse_field(r"UniqueVisited:\s*(\d+)", s_text, 0, int)
            expansions = parse_field(r"TotalExpansions:\s*(\d+)", s_text, 0, int)
            best_raw = parse_field(r"BestRaw:\s*([-+]?\d*\.?\d+)", s_text, -1e9, float)
            relaxed_gens = parse_field(r"RelaxedGens:\s*(\d+)", s_text, 0, int)
            fraction_relaxed = parse_field(r"FractionRelaxed:\s*([-+]?\d*\.?\d+)", s_text, 0.0, float)
            switch_count = parse_field(r"SwitchCount:\s*(\d+)", s_text, 0, int)
        else:
            m_raw = re.findall(r"\(Step2-BestRaw Gen: \d+ Exp: \d+ Ever: ([-+]?\d*\.?\d+)", out)
            if m_raw:
                best_raw = float(m_raw[-1])
                
        m_gen = re.findall(
            r"\(Step2-GenStats Gen: \d+ Exp: \d+ BestRaw: ([-+]?\d*\.?\d+) Literals: (\d+) BestPen: ([-+]?\d*\.?\d+)",
            out
        )
        if m_gen:
            best_pen = float(m_gen[-1][2])
            literals = int(m_gen[-1][1])
            
        evals_matches = re.findall(r"\(OptimizedDeme:\s*(\d+)\)", out)
        total_evals = sum(int(x) for x in evals_matches) if evals_matches else 0
        
        m_final = re.search(r"\(FinalResult\s*\(\(\((.*?)\)\s*([-+]?\d+)\)", out)
        final_rescored_raw = float(m_final.group(2)) if m_final else best_raw
        
        solved = (best_raw == 0.0)
        breakout = (best_raw >= -2.0)
        termination = "converged" if solved else "budget_exhausted"
        
        return {
            "problem": "parity4",
            "arm": arm_name,
            "seed": seed,
            "max_gen": MAX_GEN,
            "budget_multiplier": BUDGET_MULT,
            "best_raw": best_raw,
            "final_rescored_raw": final_rescored_raw,
            "best_pen": best_pen,
            "literals": literals,
            "total_evals": total_evals,
            "wall_time": wall_time,
            "expansions": expansions,
            "unique_visited": unique_visited,
            "relaxed_gens": relaxed_gens,
            "fraction_relaxed": fraction_relaxed,
            "switch_count": switch_count,
            "solved": solved,
            "breakout": breakout,
            "termination": termination,
            "status": "ok"
        }
    except subprocess.TimeoutExpired:
        return {
            "problem": "parity4",
            "arm": arm_name,
            "seed": seed,
            "max_gen": MAX_GEN,
            "budget_multiplier": BUDGET_MULT,
            "wall_time": time.time() - t0,
            "solved": False,
            "breakout": False,
            "termination": "timeout",
            "status": "timeout"
        }
    except Exception as e:
        return {
            "problem": "parity4",
            "arm": arm_name,
            "seed": seed,
            "max_gen": MAX_GEN,
            "budget_multiplier": BUDGET_MULT,
            "wall_time": time.time() - t0,
            "solved": False,
            "breakout": False,
            "termination": "error",
            "status": "error",
            "error_msg": str(e)
        }

def save_atomic(data, path):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)

def main():
    existing_data = []
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE) as f:
                existing_data = json.load(f)
            print(f"Loaded {len(existing_data)} existing runs from {OUTPUT_FILE}")
        except Exception:
            existing_data = []
            
    completed_keys = {(r["arm"], r["seed"]) for r in existing_data if r.get("status") == "ok"}
    
    # Also load 1x budget baseline (MaxGen=15) from stall_relaxation_results.json for comparison if available
    stall_path = os.path.join(REPO_DIR, "stall_relaxation_results.json")
    if os.path.exists(stall_path):
        try:
            with open(stall_path) as f:
                stall_data = json.load(f)
            for r in stall_data:
                if r["problem"] == "parity4" and r["arm"] in ARMS and r["seed"] in SEEDS:
                    key = (r["arm"], r["seed"], 1)
                    if not any(x.get("arm") == r["arm"] and x.get("seed") == r["seed"] and x.get("budget_multiplier") == 1 for x in existing_data):
                        r_copy = dict(r)
                        r_copy["budget_multiplier"] = 1
                        r_copy["termination"] = "converged" if r.get("solved") else "budget_exhausted"
                        existing_data.append(r_copy)
            save_atomic(existing_data, OUTPUT_FILE)
        except Exception as e:
            print(f"Notice: could not load 1x baseline: {e}")
            
    all_runs = []
    for arm in ARMS:
        for seed in SEEDS:
            if (arm, seed) not in completed_keys:
                all_runs.append((arm, seed))
                
    print(f"Total 3x Budget runs scheduled: {len(all_runs)} (Completed so far: {len(completed_keys)}/20)")
    if not all_runs:
        print("All budget check runs already completed!")
        return

    results = list(existing_data)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(run_single, arm, seed): (arm, seed) for arm, seed in all_runs}
        for future in as_completed(futures):
            arm, seed = futures[future]
            res = future.result()
            results.append(res)
            save_atomic(results, OUTPUT_FILE)
            status_str = f"Raw={res.get('best_raw', 'N/A')} Solved={res.get('solved')} Breakout={res.get('breakout')} Evals={res.get('total_evals', 0)} ({res['wall_time']:.1f}s)"
            print(f"[{res['status'].upper()}] parity4 {arm} s={seed} -> {status_str}")

if __name__ == "__main__":
    main()
