import subprocess
import re
import time
import json
import argparse
from typing import Dict, Any, List

def run_single_experiment(problem: str, complexity_ratio: float, seed: int, max_gen: int = 5) -> Dict[str, Any]:
    extra_args = [
        f"--seed={seed}",
        f"--complexityRatio={complexity_ratio}",
    ]
    if problem == "majority7":
        extra_args += ["--inputFile=majority7.csv", "--targetFeature=Out"]
    else:
        extra_args += [f"--problem={problem}"]
        
    cmd = [
        "sh",
        "/home/nonplds/projects/metta-projects/PeTTa/run.sh",
        "moses.metta",
        "-s",
        f"--maxGen={max_gen}",
        "--nDeme=1",
    ] + extra_args

    t0 = time.time()
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd="/home/nonplds/projects/metta-projects/metta-moses-representation"
    )
    elapsed = time.time() - t0
    output = proc.stdout

    # Extract selected trees per generation
    # Pattern: (SelectedTree: <tree>)
    selected_trees = re.findall(r"\(SelectedTree:\s*(.+?)\)\s*(?:\(GeneratedList|\n)", output)
    
    # Check for duplicate expansions across generations
    seen_trees = set()
    duplicate_expansions = []
    for t in selected_trees:
        cleaned_t = t.strip()
        if cleaned_t in seen_trees:
            duplicate_expansions.append(cleaned_t)
        seen_trees.add(cleaned_t)

    # Extract score progression
    scores = re.findall(r"New best score:\s*([-\d\.]+)", output)
    
    # Extract final results and raw scores:
    # FinalResult (((<tree>) <raw_score>) ...)
    final_res_block = ""
    res_match = re.search(r"\(FinalResult\s*\((.*?)\)\)\s*\)", output, re.DOTALL)
    if res_match:
        final_res_block = res_match.group(1)
    
    # Parse pairs in final result: e.g. `(Tree <raw>)`
    raw_scores = []
    for item in re.findall(r"\)\s*([-\d]+)\s*\)", final_res_block):
        try:
            raw_scores.append(int(item))
        except ValueError:
            pass
            
    best_raw = max(raw_scores) if raw_scores else None
    best_pen = max([float(s) for s in scores]) if scores else None
    perfect = (best_raw == 0)

    return {
        "problem": problem,
        "complexity_ratio": complexity_ratio,
        "seed": seed,
        "max_gen": max_gen,
        "elapsed": round(elapsed, 2),
        "selected_trees": selected_trees,
        "num_duplicate_expansions": len(duplicate_expansions),
        "duplicate_expansions": duplicate_expansions,
        "best_raw_score": best_raw,
        "best_penalized_score": best_pen,
        "perfect_found": perfect,
        "score_progression": scores,
        "raw_scores_sample": raw_scores[:5]
    }

def main():
    parser = argparse.ArgumentParser(description="MOSES Step 1 Complexity Ratio Sweep")
    parser.add_argument("--problems", type=str, default="parity4,majority5", help="Comma-separated problem names")
    parser.add_argument("--ratios", type=str, default="3.5,10,20,50", help="Comma-separated complexity ratios")
    parser.add_argument("--seeds", type=str, default="1,2,3,4,5", help="Comma-separated seeds")
    parser.add_argument("--maxGen", type=int, default=5, help="Number of generations")
    parser.add_argument("--out", type=str, default="step1_sweep_results.json", help="Output JSON results file")
    args = parser.parse_args()

    problems = [p.strip() for p in args.problems.split(",") if p.strip()]
    ratios = [float(r.strip()) for r in args.ratios.split(",") if r.strip()]
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]

    all_results = []
    print("=" * 80)
    print("MOSES STEP 1 COMPLEXITY RATIO SWEEP")
    print(f"Problems: {problems}")
    print(f"Ratios:   {ratios}")
    print(f"Seeds:    {seeds}")
    print(f"MaxGen:   {args.maxGen}")
    print("=" * 80)

    for prob in problems:
        print(f"\n>>> Running problem: {prob} <<<")
        for cr in ratios:
            for s in seeds:
                res = run_single_experiment(prob, cr, s, max_gen=args.maxGen)
                all_results.append(res)
                perf_mark = "[PERFECT 0!]" if res["perfect_found"] else ""
                re_exp = f"Re-expanded: {res['num_duplicate_expansions']}x" if res['num_duplicate_expansions'] > 0 else "No re-expansions"
                print(f"  [CR={cr:<4} Seed={s}] BestRaw: {str(res['best_raw_score']):<4} BestPen: {str(res['best_penalized_score']):<7} {re_exp:<20} Elapsed: {res['elapsed']}s {perf_mark}")

    with open(args.out, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nAll results saved to {args.out}")

if __name__ == "__main__":
    main()
