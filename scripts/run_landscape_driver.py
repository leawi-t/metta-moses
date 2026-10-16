import os
import sys
import json
import time
import subprocess

REPO_DIR = "/home/nonplds/projects/metta-projects/metta-moses-representation"
PETTA_RUNNER = "/home/nonplds/projects/metta-projects/PeTTa/run.sh"

EXEMPLARS = [
    ("E1", "Seed7"),
    ("E2", "Seed11"),
    ("E3", "Seed21"),
    ("E4", "Seed29"),
    ("E5", "Seed29_final")
]

def run_single(target, label):
    cmd = [
        "bash",
        PETTA_RUNNER,
        "scripts/eval_single_exemplar.metta",
        "-s",
        f"--targetExemplar={target}"
    ]
    print(f"\n>>> Running Exemplar {target} ({label})...", flush=True)
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    elapsed = time.time() - t0
    print(f">>> Exemplar {target} completed in {elapsed:.1f}s (Exit code: {proc.returncode})", flush=True)
    
    # Check if partial json was produced
    json_path = os.path.join(REPO_DIR, f"landscape_{target}.json")
    if os.path.exists(json_path):
        with open(json_path) as f:
            data = json.load(f)
        return data
    else:
        print(f"ERROR: {json_path} was not created! Process stderr:\n{proc.stderr}\nStdout tail:\n{proc.stdout[-500:]}", flush=True)
        return None


def main():
    print("=" * 80)
    print("STARTING MULTI-EXEMPLAR KNOB-FLIP LANDSCAPE ANALYSIS (E1 - E5)")
    print("Hamming Distances: d=1 (exhaustive ~600), d=2 (500 samples), d=3 (500 samples)")
    print("=" * 80)
    
    aggregated = {}
    
    for target, label in EXEMPLARS:
        res = run_single(target, label)
        if res:
            key = f"{target}_{label}"
            aggregated[key] = res
            
    # Save aggregate results
    output_path = os.path.join(REPO_DIR, "knob_landscape_results.json")
    with open(output_path, "w") as f:
        json.dump(aggregated, f, indent=2)
        
    print("\n" + "=" * 80)
    print("KNOB-FLIP LANDSCAPE SWEEP SUMMARY (Across Raw -2.0 Exemplars)")
    print("=" * 80)
    
    header = f"{'Exemplar':<16} | {'Dist':<4} | {'Total':<6} | {'Raw+ / Pen+':<12} | {'Raw+ / Pen-':<12} | {'Neutral/Worse':<14} | {'Max Raw':<7}"
    print(header)
    print("-" * len(header))
    
    for key, data in aggregated.items():
        c_raw = data.get("center_raw", -2.0)
        c_pen = data.get("center_pen", 0.0)
        print(f"[{key}] Center Raw={c_raw} Pen={c_pen:.3f}:")
        for dk in ["dist1", "dist2", "dist3"]:
            st = data[dk]
            if st["total"] == 0:
                continue
            dist_num = dk.replace("dist", "d=")
            tot = st["total"]
            climbable = st["raw_improving_pen_improving"]
            blocked = st["raw_improving_pen_worsening"]
            worse = st["neutral_or_worse"]
            max_r = st["max_raw"]
            print(f"{'':<16} | {dist_num:<4} | {tot:<6} | {climbable:<12} | {blocked:<12} | {worse:<14} | {max_r:<7}")
            
    print("=" * 80)
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    main()
