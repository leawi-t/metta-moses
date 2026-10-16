import os
import shutil
import subprocess
import re
import json
import time

REPO_DIR = "/home/nonplds/projects/metta-projects/metta-moses-representation"
PETTA_RUNNER = "/home/nonplds/projects/metta-projects/PeTTa/run.sh"

def set_reducer_mode(mode):
    assert mode in ("patched", "unpatched")
    src_dih = os.path.join(REPO_DIR, f"reduct/boolean-reduct/delete-inconsistent-handle.metta.{mode}")
    dst_dih = os.path.join(REPO_DIR, "reduct/boolean-reduct/delete-inconsistent-handle.metta")
    shutil.copyfile(src_dih, dst_dih)
    
    src_rte = os.path.join(REPO_DIR, f"reduct/boolean-reduct/reduce-to-elegance.metta.{mode}")
    dst_rte = os.path.join(REPO_DIR, "reduct/boolean-reduct/reduce-to-elegance.metta")
    shutil.copyfile(src_rte, dst_rte)

def run_moses_instance(problem, seed, max_gen=5):
    cmd = [
        "bash",
        PETTA_RUNNER,
        "moses.metta",
        "-s",
        f"--problem={problem}",
        f"--maxGen={max_gen}",
        "--complexityRatio=3.5",
        "--maxRevisits=1",
        f"--seed={seed}"
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    elapsed = time.time() - t0
    out = proc.stdout
    
    # Parse Step2-Summary
    m_sum = re.search(r"\(Step2-Summary UniqueVisited:\s*(\d+)\s*TotalExpansions:\s*(\d+)\s*FallbackCount:\s*(\d+)\s*BestRaw:\s*([-+]?\d*\.?\d+)\s*BetterRawWorsePen:\s*(\d+)\s*(?:DistinctCulledBetterRaw:\s*(\d+)\s*)?Culled:\s*(\d+)\s*Levels:\s*\[(.*?)\]\)", out)
    
    best_raw = -1e9
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
            
    # Parse candidate count from CandidateCollectorSummary
    m_cand = re.search(r"total_candidates\s+(\d+)", out)
    cands = int(m_cand.group(1)) if m_cand else 0
    
    # Parse final exemplar
    m_exemplar = re.search(r"\(SelectedTree:\s*(.*?)\)", out)
    final_exemplar = m_exemplar.group(1) if m_exemplar else "N/A"
    
    return {
        "best_raw": best_raw,
        "expansions": expansions,
        "unique_visited": unique_visited,
        "total_cands": cands,
        "final_exemplar": final_exemplar,
        "elapsed": elapsed
    }

def run_differential_study():
    problems = ["parity4", "majority5", "disjunction3"]
    seeds = [7, 11, 21, 29, 42]
    
    results = []
    
    try:
        print("="*90)
        print("DIFFERENTIAL BENCHMARK: UNPATCHED VS PATCHED REDUCT ACROSS PAIRED SEEDS")
        print("="*90)
        print(f"{'Problem':<15} {'Seed':<6} {'Patched Raw':<14} {'Unpatched Raw':<15} {'Raw Delta':<12} {'Patched Cands':<15} {'Unpatched Cands':<17} {'Endpoint Match'}")
        print("-" * 105)
        
        for prob in problems:
            for seed in seeds:
                # 1. Run Patched
                set_reducer_mode("patched")
                res_patched = run_moses_instance(prob, seed, max_gen=5)
                
                # 2. Run Unpatched
                set_reducer_mode("unpatched")
                res_unpatched = run_moses_instance(prob, seed, max_gen=5)
                
                raw_delta = res_patched["best_raw"] - res_unpatched["best_raw"]
                endpoint_match = "IDENTICAL" if raw_delta == 0 and res_patched["final_exemplar"] == res_unpatched["final_exemplar"] else ("SAME SCORE" if raw_delta == 0 else f"DIFF ({raw_delta:+.1f})")
                
                row = {
                    "problem": prob,
                    "seed": seed,
                    "patched_raw": res_patched["best_raw"],
                    "unpatched_raw": res_unpatched["best_raw"],
                    "raw_delta": raw_delta,
                    "patched_cands": res_patched["total_cands"],
                    "unpatched_cands": res_unpatched["total_cands"],
                    "endpoint_match": endpoint_match,
                    "patched_exemplar": res_patched["final_exemplar"],
                    "unpatched_exemplar": res_unpatched["final_exemplar"]
                }
                results.append(row)
                
                print(f"{prob:<15} {seed:<6} {res_patched['best_raw']:<14.1f} {res_unpatched['best_raw']:<15.1f} {raw_delta:<12.1f} {res_patched['total_cands']:<15} {res_unpatched['total_cands']:<17} {endpoint_match}")
                
        with open("reduct_differential_results.json", "w") as f:
            json.dump(results, f, indent=2)
            
    finally:
        # Always restore repository to patched mode
        set_reducer_mode("patched")
        print("\n[INFO] Restored repository to PATCHED reduct mode.")

if __name__ == "__main__":
    run_differential_study()
