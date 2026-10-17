#!/usr/bin/env python3
"""
Step 3: 2x3 Factorial Benchmark Runner on Parity4.

Design:
Factor A (Generator):
  - original (permPolarityMode=classic)
  - full_negation (permPolarityMode=symmetric)
Factor B (Complexity Ratio):
  - static_14
  - static_100
  - stall_relax_K5

Replication: 30 paired seeds (seeds 1-30). Total: 2 x 3 x 30 = 180 runs.
Saves progress atomically to factorial_2x3_results.json.
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
OUTPUT_FILE = os.path.join(REPO_DIR, "factorial_2x3_results.json")

GENERATORS = {
    "original": ["--permPolarityMode=classic"],
    "full_negation": ["--permPolarityMode=symmetric"]
}

RATIO_ARMS = {
    "static_14": {
        "flags": ["--complexityRatio=14.0", "--stallRelaxationMode=False"]
    },
    "static_100": {
        "flags": ["--complexityRatio=100.0", "--stallRelaxationMode=False"]
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
        ]
    }
}

SEEDS = list(range(1, 31)) # 30 paired seeds
MAX_GEN = 15

def parse_field(pattern, text, default=None, cast=int):
    m = re.search(pattern, text)
    if m:
        try:
            return cast(m.group(1))
        except Exception:
            pass
    return default

def run_single(gen_name, arm_name, seed):
    gen_flags = GENERATORS[gen_name]
    arm_flags = RATIO_ARMS[arm_name]["flags"]
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
    ] + gen_flags + arm_flags
    
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=400
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
        
        return {
            "problem": "parity4",
            "generator": gen_name,
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
            "problem": "parity4",
            "generator": gen_name,
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
            "problem": "parity4",
            "generator": gen_name,
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
            
    completed_keys = {(r.get("generator", "original"), r["arm"], r["seed"]) for r in existing_data if r.get("status") == "ok"}
    
    # We can also reuse the original generator runs for seeds 1-20 from stall_relaxation_results.json
    stall_path = os.path.join(REPO_DIR, "stall_relaxation_results.json")
    if os.path.exists(stall_path):
        try:
            with open(stall_path) as f:
                stall_data = json.load(f)
            for r in stall_data:
                if r["problem"] == "parity4" and r["arm"] in RATIO_ARMS and r["seed"] <= 20:
                    key = ("original", r["arm"], r["seed"])
                    if key not in completed_keys:
                        r_copy = dict(r)
                        r_copy["generator"] = "original"
                        existing_data.append(r_copy)
                        completed_keys.add(key)
            save_atomic(existing_data, OUTPUT_FILE)
            print(f"Imported baseline seeds 1-20 for 'original' generator ({len(completed_keys)} total completed).")
        except Exception as e:
            print(f"Notice: could not import original runs: {e}")
            
    all_runs = []
    for gen in GENERATORS:
        for arm in RATIO_ARMS:
            for seed in SEEDS:
                if (gen, arm, seed) not in completed_keys:
                    all_runs.append((gen, arm, seed))
                    
    total_cells = len(GENERATORS) * len(RATIO_ARMS) * len(SEEDS)
    print(f"2x3 Factorial Scheduled: {len(all_runs)} runs to execute ({len(completed_keys)}/{total_cells} completed).")
    if not all_runs:
        print("All 2x3 factorial runs already completed!")
        return

    results = list(existing_data)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(run_single, gen, arm, seed): (gen, arm, seed) for gen, arm, seed in all_runs}
        for future in as_completed(futures):
            gen, arm, seed = futures[future]
            res = future.result()
            results.append(res)
            save_atomic(results, OUTPUT_FILE)
            status_str = f"Raw={res.get('best_raw', 'N/A')} Solved={res.get('solved')} Break={res.get('breakout')} ({res['wall_time']:.1f}s)"
            print(f"[{res['status'].upper()}] {gen} {arm} s={seed} -> {status_str}")

if __name__ == "__main__":
    main()
