import json
from collections import defaultdict
import numpy as np

with open("dense_ratio_sweep_results.json") as f:
    data = json.load(f)

print(f"Total completed runs so far: {len(data)}")

by_group = defaultdict(list)
for r in data:
    by_group[(r["problem"], r["ratio"])].append(r)

print(f"{'Problem':<12} {'Ratio':<8} {'N':<4} {'Mean Raw':<10} {'Median Raw':<12} {'Break Rate':<12} {'Solve Rate':<12} {'Mean Lits':<10}")
print("-" * 90)

for (prob, r), rows in sorted(by_group.items()):
    raws = [x["best_raw"] for x in rows]
    breaks = [1 if x["breakout"] else 0 for x in rows]
    solves = [1 if x["solved"] else 0 for x in rows]
    lits = [x["literals"] for x in rows]
    
    mean_raw = np.mean(raws)
    med_raw = np.median(raws)
    break_rate = np.mean(breaks)
    solve_rate = np.mean(solves)
    mean_lits = np.mean(lits)
    
    print(f"{prob:<12} {r:<8.1f} {len(rows):<4} {mean_raw:<10.2f} {med_raw:<12.1f} {break_rate*100:<11.1f}% {solve_rate*100:<11.1f}% {mean_lits:<10.1f}")
