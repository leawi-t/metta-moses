import subprocess
import re
import time

def run_metta_moses(extra_args: list[str], max_gen: int = 4):
    cmd = [
        "sh",
        "/home/nonplds/projects/metta-projects/PeTTa/run.sh",
        "moses.metta",
        "-s",
        f"--maxGen={max_gen}",
        "--nDeme=1",
    ] + extra_args
    
    t0 = time.time()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd="/home/nonplds/projects/metta-projects/metta-moses-representation")
    elapsed = time.time() - t0
    output = proc.stdout
    
    # Extract best scores from output
    # (New best score: -6.0)
    scores = re.findall(r"New best score:\s*([-\d\.]+)", output)
    # Extract final results: (FinalResult (((... ) -3) ...))
    final_matches = re.findall(r"\((FinalResult\s*\(.*?\)\)\))", output, re.DOTALL)
    
    # Raw scores in final result: e.g. `) -3)` or `) 0)`
    raw_scores = re.findall(r"\)\s*([-\d]+)\s*\)", output)
    
    return {
        "elapsed": round(elapsed, 1),
        "scores": scores,
        "raw_scores": raw_scores,
        "output_tail": output[-500:] if len(output) > 500 else output
    }

def main():
    ratios = [3.5, 7.0, 14.0, 100000.0]
    
    print("=" * 70)
    print("METTA-MOSES COMPLEXITY SWEEP: MAJORITY-5")
    print("=" * 70)
    for cr in ratios:
        args = [f"--problem=majority5", f"--complexityRatio={cr}"]
        res = run_metta_moses(args, max_gen=4)
        print(f"\nComplexityRatio: {cr} (Elapsed: {res['elapsed']}s)")
        print(f"  Score progression: {res['scores']}")
        print(f"  Final raw scores sample: {res['raw_scores'][:5]}")

    print("\n" + "=" * 70)
    print("METTA-MOSES COMPLEXITY SWEEP: MAJORITY-7")
    print("=" * 70)
    for cr in ratios:
        args = ["--inputFile=majority7.csv", "--targetFeature=Out", f"--complexityRatio={cr}"]
        res = run_metta_moses(args, max_gen=3)
        print(f"\nComplexityRatio: {cr} (Elapsed: {res['elapsed']}s)")
        print(f"  Score progression: {res['scores']}")
        print(f"  Final raw scores sample: {res['raw_scores'][:5]}")

if __name__ == "__main__":
    main()
