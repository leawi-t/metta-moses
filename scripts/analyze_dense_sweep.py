import json
from collections import defaultdict, Counter

data = json.load(open("dense_ratio_sweep_results.json"))
print(f"Total entries in file: {len(data)}")

status_counts = Counter(d.get("status") for d in data)
print("Status breakdown:", status_counts)

# Check unique (problem, ratio, seed)
seen = set()
duplicates = 0
for d in data:
    k = (d["problem"], float(d["ratio"]), int(d["seed"]))
    if k in seen:
        duplicates += 1
    seen.add(k)

print(f"Unique runs: {len(seen)} / 360 | Duplicates: {duplicates}")

# Check missing keys if any
problems = ["parity4", "majority5", "parity5"]
ratios = [14.0, 20.0, 50.0, 100.0, 300.0, 1000.0]
seeds = list(range(1, 21))

missing = []
for p in problems:
    for r in ratios:
        for s in seeds:
            if (p, r, s) not in seen:
                missing.append((p, r, s))

print(f"Missing runs count: {len(missing)}")
if missing:
    print(f"Missing: {missing[:10]}")
