import json
from collections import defaultdict
import numpy as np

data = json.load(open("dense_ratio_sweep_results.json"))

# Group by (problem, ratio)
results = defaultdict(dict)
for d in data:
    if d.get("status") == "ok":
        p = d["problem"]
        r = float(d["ratio"])
        s = int(d["seed"])
        results[(p, r)][s] = d

problems = ["parity4", "parity5", "majority5"]
ratios = [14.0, 20.0, 50.0, 100.0, 300.0, 1000.0]

print("### DENSE RATIO SWEEP DETAILED ANALYSIS (Paired Seeds 1-20)\n")

for p in problems:
    print(f"#### Problem: `{p}`")
    print(f"| Ratio | N (ok) | Mean Raw (SD) | Median Raw | Breakout Rate | Solve Rate | Mean Lits (SD) | Mean Evals | Mean Time (s) |")
    print(f"|---|---|---|---|---|---|---|---|---|")
    
    for r in ratios:
        runs = list(results[(p, r)].values())
        if not runs:
            continue
        n = len(runs)
        raws = [x["best_raw"] for x in runs]
        breaks = [1 if x["breakout"] else 0 for x in runs]
        solves = [1 if x["solved"] else 0 for x in runs]
        lits = [x["literals"] for x in runs]
        evals = [x["total_evals"] for x in runs]
        times = [x["wall_time"] for x in runs]
        
        mean_raw = np.mean(raws)
        std_raw = np.std(raws)
        med_raw = np.median(raws)
        break_rate = np.mean(breaks) * 100
        solve_rate = np.mean(solves) * 100
        mean_lits = np.mean(lits)
        std_lits = np.std(lits)
        mean_evals = np.mean(evals)
        mean_time = np.mean(times)
        
        print(f"| {r:.1f} | {n} | {mean_raw:.2f} (±{std_raw:.2f}) | {med_raw:.1f} | {break_rate:.1f}% | {solve_rate:.1f}% | {mean_lits:.1f} (±{std_lits:.1f}) | {mean_evals:.0f} | {mean_time:.1f}s |")
    print()

print("\n#### Paired Dose-Response Progression (Paired by Seed across Ratios)")
for p in problems:
    print(f"\n##### Problem: `{p}` (Paired Seeds across Ratios)")
    # Find seeds that completed across all ratios
    common_seeds = set(range(1, 21))
    for r in ratios:
        common_seeds &= set(results[(p, r)].keys())
    common_seeds = sorted(list(common_seeds))
    print(f"Seeds with full paired coverage across all 6 ratios: {len(common_seeds)} seeds ({common_seeds})")
    
    print(f"| Seed | r=14 | r=20 | r=50 | r=100 | r=300 | r=1000 | Max Gain vs r=14 |")
    print(f"|---|---|---|---|---|---|---|---|")
    for s in common_seeds:
        row = [results[(p, r)][s]["best_raw"] for r in ratios]
        max_gain = max(row) - row[0]
        print(f"| {s:2d} | {row[0]:.1f} | {row[1]:.1f} | {row[2]:.1f} | {row[3]:.1f} | {row[4]:.1f} | {row[5]:.1f} | +{max_gain:.1f} |")
