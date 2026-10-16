import subprocess
import re
import sys

def run_and_count(problem, seed, max_gen=3):
    cmd = [
        "bash",
        "/home/nonplds/projects/metta-projects/PeTTa/run.sh",
        "moses.metta",
        "-s",
        f"--problem={problem}",
        f"--maxGen={max_gen}",
        "--complexityRatio=3.5",
        "--maxRevisits=1",
        f"--seed={seed}"
    ]
    proc = subprocess.run(cmd, cwd="/home/nonplds/projects/metta-projects/metta-moses-representation", stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out = proc.stdout
    
    empty_or = len(re.findall(r"CASE-EMPTY-OR", out))
    residual_or_false = len(re.findall(r"CASE-RESIDUAL-OR-FALSE", out))
    remaining = len(re.findall(r"CASE-REMAINING-CHILDREN", out))
    
    gen_matches = re.findall(r"Iteration (\d+) running", out)
    gens = len(set(gen_matches))
    
    # Also check if any CASE-RESIDUAL-OR-FALSE line has details
    residuals = re.findall(r"\(CASE-RESIDUAL-OR-FALSE Parent: (.*?) Current: (.*?) withoutPOA: (.*?)\)", out)
    
    return {
        "problem": problem,
        "seed": seed,
        "gens": gens,
        "empty_or": empty_or,
        "residual_or_false": residual_or_false,
        "remaining": remaining,
        "total_or_inconsistencies": empty_or + residual_or_false + remaining,
        "residuals": residuals
    }

if __name__ == "__main__":
    problems = ["parity4", "majority5", "disjunction3"]
    seeds = [7, 11, 21]
    
    print(f"{'Problem':<15} {'Seed':<6} {'Gens':<6} {'Empty-OR (24c4)':<18} {'Residual (OR FALSE)':<22} {'Remaining':<12} {'Total Incons':<12}")
    print("-" * 95)
    
    for prob in problems:
        for s in seeds:
            res = run_and_count(prob, s, max_gen=3)
            print(f"{res['problem']:<15} {res['seed']:<6} {res['gens']:<6} {res['empty_or']:<18} {res['residual_or_false']:<22} {res['remaining']:<12} {res['total_or_inconsistencies']:<12}")
            if res['residuals']:
                for r in res['residuals'][:3]:
                    print(f"   Sample residual -> Parent: {r[0]} | withoutPOA: {r[2]}")
