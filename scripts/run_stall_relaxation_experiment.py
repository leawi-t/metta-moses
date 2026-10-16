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

ARMS = {
    "static_14": {
        "flags": ["--complexityRatio=14.0", "--stallRelaxationMode=False"],
        "desc": "Baseline static ratio 14.0"
    },
    "static_100": {
        "flags": ["--complexityRatio=100.0", "--stallRelaxationMode=False"],
        "desc": "Static relaxed upper bound 100.0"
    },
    "stall_relax_K3": {
        "flags": [
            "--stallRelaxationMode=dynamic",
            "--baseComplexityRatio=14.0",
            "--relaxedComplexityRatio=100.0",
            "--stallThresholdK=3",
            "--relaxWindowMinM=3",
            "--relaxGraceG=2",
            "--relaxCooldownC=3"
        ],
        "desc": "Stall-triggered relaxation (K=3, M=3, G=2, C=3)"
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

PROBLEMS = ["parity4", "majority5", "parity5"]
SEEDS = list(range(1, 21)) # 20 paired seeds

def parse_field(pattern, text, default=None, cast=int):
    m = re.search(pattern, text)
    if m:
        try:
            return cast(m.group(1))
        except Exception:
            pass
    return default

def run_single(problem, arm_name, seed, max_gen):
    arm_cfg = ARMS[arm_name]
    cmd = [
        "bash",
        PETTA_RUNNER,
        "moses.metta",
        "-s",
        f"--problem={problem}",
        f"--maxGen={max_gen}",
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
            timeout=360
        )
        wall_time = time.time() - t0
        out = proc.stdout
        
        # Summary metrics
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
        
        # Verify FinalResult
        m_final = re.search(r"\(FinalResult\s*\(\(\((.*?)\)\s*([-+]?\d+)\)", out)
        final_rescored_raw = float(m_final.group(2)) if m_final else best_raw
        
        # Breakout definitions (pre-registered):
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
            "arm": arm_name,
            "seed": seed,
            "max_gen": max_gen,
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
            "problem": problem,
            "arm": arm_name,
            "seed": seed,
            "max_gen": max_gen,
            "best_raw": -1e9,
            "status": "timeout"
        }
    except Exception as e:
        return {
            "problem": problem,
            "arm": arm_name,
            "seed": seed,
            "max_gen": max_gen,
            "best_raw": -1e9,
            "status": f"error: {str(e)}"
        }

def run_experiment():
    output_file = os.path.join(REPO_DIR, "stall_relaxation_results.json")
    all_results = []
    completed_keys = set()
    
    if os.path.exists(output_file):
        try:
            with open(output_file) as f:
                all_results = json.load(f)
            for r in all_results:
                if r.get("status") in ("ok", "timeout"):
                    completed_keys.add((r["problem"], r["arm"], int(r["seed"])))
            print(f"Loaded {len(all_results)} existing runs ({len(completed_keys)} unique completed). Resuming...", flush=True)
        except Exception as e:
            print(f"Warning: could not read {output_file}: {e}", flush=True)
            
    tasks = []
    for prob in PROBLEMS:
        mg = 15 if prob in ("parity4", "majority5") else 10
        for arm_name in ARMS:
            for s in SEEDS:
                if (prob, arm_name, int(s)) not in completed_keys:
                    tasks.append((prob, arm_name, s, mg))
                    
    total_tasks = len(PROBLEMS) * len(ARMS) * len(SEEDS)
    print(f"Total tasks: {total_tasks} | Completed: {len(completed_keys)} | Remaining: {len(tasks)}", flush=True)
    print(f"Arms: {list(ARMS.keys())}", flush=True)
    print(f"Problems: {PROBLEMS}", flush=True)
    
    if not tasks:
        print("All runs completed! Analyzing...", flush=True)
        return
        
    completed = len(completed_keys)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(run_single, prob, arm, s, mg): (prob, arm, s, mg)
            for (prob, arm, s, mg) in tasks
        }
        
        for future in as_completed(futures):
            res = future.result()
            all_results.append(res)
            completed += 1
            if res["status"] == "ok":
                print(f"[{completed:3d}/{total_tasks}] {res['problem']:<10} {res['arm']:<18} s={res['seed']:<2} -> Raw={res['best_raw']:<5.1f} Lits={res['literals']:<2} Evals={res['total_evals']:<5} FracRel={res['fraction_relaxed']:.2f} Break={res['breakout']} ({res['wall_time']:.1f}s)", flush=True)
            else:
                print(f"[{completed:3d}/{total_tasks}] {res['problem']:<10} {res['arm']:<18} s={res['seed']:<2} -> STATUS: {res['status']}", flush=True)
                
            # Save progress after every run atomically so that no progress is lost on sleep/shutdown
            try:
                tmp_file = output_file + ".tmp"
                with open(tmp_file, "w") as f:
                    json.dump(all_results, f, indent=2)
                os.replace(tmp_file, output_file)
            except Exception as e:
                print(f"Error saving progress: {e}", flush=True)

if __name__ == "__main__":
    run_experiment()
