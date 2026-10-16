import json
from collections import defaultdict
import numpy as np
from scipy import stats

data = json.load(open("dense_ratio_sweep_results.json"))

# Group by (problem, ratio, seed)
runs = defaultdict(dict)
for d in data:
    p = d["problem"]
    r = float(d["ratio"])
    s = int(d["seed"])
    # If duplicate, prefer "ok"
    if s not in runs[(p, r)] or d.get("status") == "ok":
        runs[(p, r)][s] = d

problems = ["parity4", "parity5", "majority5"]
ratios_low = [14.0, 20.0, 50.0]
ratios_high = [100.0, 300.0, 1000.0]
all_ratios = ratios_low + ratios_high

print("=" * 80)
print("1. POOLED REGIME ANALYSIS & CONSERVATIVE BREAKOUT RATES (Timeouts = Failures)")
print("=" * 80)

for p in problems:
    print(f"\n--- Problem: {p} ---")
    
    # Per-ratio summary with conservative N=20
    print(f"{'Ratio':<8} {'OK/Total':<10} {'Conserv Break%':<16} {'Conserv Solve%':<16} {'Mean Lits':<12} {'Timeouts':<10}")
    for r in all_ratios:
        cell_runs = [runs[(p, r)].get(s) for s in range(1, 21)]
        ok_runs = [x for x in cell_runs if x and x.get("status") == "ok"]
        timeouts = sum(1 for x in cell_runs if x and "timed out" in x.get("status", ""))
        
        # Conservative: timeout is counted as NOT breakout, NOT solved
        conserv_breaks = sum(1 for x in ok_runs if x.get("breakout"))
        conserv_solves = sum(1 for x in ok_runs if x.get("solved"))
        
        conserv_break_rate = conserv_breaks / 20.0 * 100
        conserv_solve_rate = conserv_solves / 20.0 * 100
        
        mean_lits = np.mean([x["literals"] for x in ok_runs]) if ok_runs else 0.0
        
        print(f"{r:<8.1f} {len(ok_runs)}/20     {conserv_break_rate:<15.1f}% {conserv_solve_rate:<15.1f}% {mean_lits:<11.1f} {timeouts:<10}")
        
    # Pooled regime comparison
    low_runs = []
    high_runs = []
    for r in ratios_low:
        for s in range(1, 21):
            x = runs[(p, r)].get(s)
            low_runs.append(x)
            
    for r in ratios_high:
        for s in range(1, 21):
            x = runs[(p, r)].get(s)
            high_runs.append(x)
            
    low_ok = [x for x in low_runs if x and x.get("status") == "ok"]
    high_ok = [x for x in high_runs if x and x.get("status") == "ok"]
    
    low_breaks = sum(1 for x in low_ok if x.get("breakout"))
    high_breaks = sum(1 for x in high_ok if x.get("breakout"))
    
    low_timeouts = sum(1 for x in low_runs if x and "timed out" in x.get("status", ""))
    high_timeouts = sum(1 for x in high_runs if x and "timed out" in x.get("status", ""))
    
    print(f"\nPOOLED REGIMES (N=60 per regime):")
    print(f"Low Regime (14, 20, 50):   Breakout = {low_breaks}/60 ({low_breaks/60.0*100:.1f}%) | Timeouts = {low_timeouts}")
    print(f"High Regime (100, 300, 1000): Breakout = {high_breaks}/60 ({high_breaks/60.0*100:.1f}%) | Timeouts = {high_timeouts}")

print("\n" + "=" * 80)
print("2. PAIRED WILCOXON SIGNED-RANK TEST (Per-Seed Paired Performance)")
print("=" * 80)

for p in problems:
    # Compute per-seed mean raw score under low regime vs high regime
    # For seeds with timeouts, use the worst observed score or score at timeout
    seed_low_raw = []
    seed_high_raw = []
    
    for s in range(1, 21):
        low_scores = []
        for r in ratios_low:
            x = runs[(p, r)].get(s)
            if x and x.get("status") == "ok":
                low_scores.append(x["best_raw"])
            else:
                low_scores.append(-16.0 if "parity" in p else -16.0) # penalty floor
                
        high_scores = []
        for r in ratios_high:
            x = runs[(p, r)].get(s)
            if x and x.get("status") == "ok":
                high_scores.append(x["best_raw"])
            else:
                high_scores.append(-16.0 if "parity" in p else -16.0)
                
        seed_low_raw.append(np.mean(low_scores))
        seed_high_raw.append(np.mean(high_scores))
        
    diff = np.array(seed_high_raw) - np.array(seed_low_raw)
    
    # Wilcoxon test
    # Check if differences are all zero
    if np.all(diff == 0):
        print(f"{p:<12}: All seed differences are 0.0 (p = 1.0)")
    else:
        stat, p_val = stats.wilcoxon(seed_high_raw, seed_low_raw)
        mean_gain = np.mean(diff)
        print(f"{p:<12}: Mean Paired Gain = {mean_gain:+.2f} | Wilcoxon W = {stat:.1f}, p-value = {p_val:.4e} {'(Significant)' if p_val < 0.05 else '(Not Significant)'}")
        for s in range(1, 21):
            print(f"   Seed {s:2d}: Low={seed_low_raw[s-1]:.2f} -> High={seed_high_raw[s-1]:.2f} (diff={diff[s-1]:+.2f})")
