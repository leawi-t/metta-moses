import subprocess
import re
import json
from concurrent.futures import ThreadPoolExecutor

SEEDS = [7, 11, 21, 29]
PETTA_RUNNER = "/home/nonplds/projects/metta-projects/PeTTa/run.sh"
REPO_DIR = "/home/nonplds/projects/metta-projects/metta-moses-representation"

def run_seed(seed):
    print(f"Starting seed {seed}...")
    cmd = [
        "bash", PETTA_RUNNER, "moses.metta", "-s",
        "--problem=parity4",
        "--maxGen=30",
        "--complexityRatio=3.5",
        "--maxRevisits=1",
        f"--seed={seed}"
    ]
    proc = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
    out = proc.stdout
    
    # Extract exemplars with raw -2
    exemplars = []
    # Pattern: (Step2-Exemplar Gen: <g> Exp: <e> Repeated: <r> Visits: <v> Raw: <raw> Pen: <pen> CanonKey: <key>)
    # and (SelectedTree: <tree>)
    blocks = re.findall(
        r"\(Step2-Exemplar Gen: (\d+) Exp: (\d+) Repeated: (\w+) Visits: (\d+) Raw: ([-+]?\d*\.?\d+) Pen: ([-+]?\d*\.?\d+) CanonKey: (.*?)\)\s*\n\(SelectedTree: (.*?)\)",
        out
    )
    for g, e, rep, v, raw, pen, ckey, tree in blocks:
        if float(raw) == -2.0:
            exemplars.append({
                "gen": int(g),
                "exp": int(e),
                "raw": float(raw),
                "pen": float(pen),
                "canon_key": ckey.strip(),
                "tree": tree.strip()
            })
            
    # Also check FinalResult: (FinalResult (((<tree> <raw>) ...)))
    final_m = re.search(r"\(FinalResult \((.*?)\)\)\n", out, re.DOTALL)
    final_trees = []
    if final_m:
        pairs = re.findall(r"\(\((.*?)\)\s+([-+]?\d*\.?\d+)\)", final_m.group(1))
        for t, r in pairs:
            if float(r) == -2.0:
                final_trees.append(t.strip())
                
    print(f"Seed {seed} finished. Found {len(exemplars)} raw -2 exemplars and {len(final_trees)} final raw -2 trees.")
    return {
        "seed": seed,
        "exemplars": exemplars,
        "final_trees": final_trees
    }

if __name__ == "__main__":
    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(run_seed, s): s for s in SEEDS}
        for fut in futures:
            s = futures[fut]
            try:
                res = fut.result()
                results[s] = res
            except Exception as e:
                print(f"Error on seed {s}: {e}")
                
    with open("raw2_exemplars.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Saved results to raw2_exemplars.json")
