import json

with open("long_horizon_parity.json") as f:
    data = json.load(f)

r2 = [d for d in data if d.get("best_raw") == -2.0]
print(f"Total entries with raw == -2.0: {len(r2)}")
for d in r2:
    print(f"Arm: {d.get('arm')} | Seed: {d.get('seed')} | MaxGen: {d.get('max_gen')} | Ratio: {d.get('ratio')}")
