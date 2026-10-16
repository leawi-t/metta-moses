import json
import os

path = "dense_ratio_sweep_results.json"
if os.path.exists(path):
    with open(path) as f:
        data = json.load(f)
    print(f"Total saved runs: {len(data)}")
    if data:
        last = data[-1]
        print(f"Latest run: {last.get('problem')} r={last.get('ratio')} s={last.get('seed')} raw={last.get('best_raw')}")
else:
    print("dense_ratio_sweep_results.json does not exist.")
