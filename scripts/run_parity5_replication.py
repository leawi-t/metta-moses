#!/usr/bin/env python3
"""
Step 2: Parity5 Fresh-Seed Replication Runner (Seeds 21-60, N=40 seeds per arm).

Evaluates whether the nominal hit of stall_relax_K5 on Parity5 replicates on fresh seeds:
1. static_14 (Baseline)
2. static_100 (Static upper bound)
3. stall_relax_K5 (Dynamic stall relaxation)
4. trigger_only_ctrl (Metapopulation rescore/re-sort causal negative control)

Saves progress atomically to parity5_replication_results.json.
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
OUTPUT_FILE = os.path.join(REPO_DIR, "parity5_replication_results.json")

ARMS = {
    "static_14": {
        "flags": ["--complexityRatio=14.0", "--stallRelaxationMode=False"],
        "desc": "Baseline static ratio 14.0"
    },
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
    },
    "trigger_only_ctrl": {
        "flags": [
            "--stallRelaxationMode=trigger_only",
            "--baseComplexityRatio=14.0",
            "--relaxedComplexityRatio=14.0",
            "--stallThresholdK=3",
            "--relaxWindowMinM=3",
            "--relaxGraceG=2",
            "--relaxCooldownC=3"
        ],
        "desc": "Trigger-only control (K=3, r=14->14 rescore control)"
    }
}

SEEDS = list(range(21, 61)) # 40 fresh independent seeds
MAX_GEN = 10

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
        "--problem=parity5",
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
            timeout=300
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
        breakout = (best_raw > -15.0)
        
        return {
            "problem": "parity5",
            "arm": arm_name,
            "seed": seed,
            "max_gen": MAX_GEN,
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
            "status": "ok"
        }
    except subprocess.TimeoutExpired:
        return {
            "problem": "parity5",
            "arm": arm_name,
            "seed": seed,
            "max_gen": MAX_GEN,
            "wall_time": time.time() - t0,
            "solved": False,
            "breakout": False,
            "status": "timeout"
        }
    except Exception as e:
        return {
            "problem": "parity5",
            "arm": arm_name,
            "seed": seed,
            "max_gen": MAX_GEN,
            "wall_time": time.time() - t0,
            "solved": False,
            "breakout": False,
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
    all_runs = []
    for arm in ARMS:
        for seed in SEEDS:
            if (arm, seed) not in completed_keys:
                all_runs.append((arm, seed))
                
    total_needed = len(ARMS) * len(SEEDS)
    print(f"Parity5 Replication Scheduled: {len(all_runs)} runs to execute ({len(completed_keys)}/{total_needed} completed).")
    if not all_runs:
        print("All replication runs already completed!")
        return

    results = list(existing_data)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(run_single, arm, seed): (arm, seed) for arm, seed in all_runs}
        for future in as_completed(futures):
            arm, seed = futures[future]
            res = future.result()
            results.append(res)
            save_atomic(results, OUTPUT_FILE)
            status_str = f"Raw={res.get('best_raw', 'N/A')} Break={res.get('breakout')} Evals={res.get('total_evals', 0)} ({res['wall_time']:.1f}s)"
            print(f"[{res['status'].upper()}] parity5 {arm} s={seed} -> {status_str}")

if __name__ == "__main__":
    main()
