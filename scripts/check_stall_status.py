import json
import os
from collections import defaultdict

filepath = "stall_relaxation_results.json"
if not os.path.exists(filepath):
    print("No runs completed yet (stall_relaxation_results.json not found).")
    exit(0)

try:
    with open(filepath) as f:
        data = json.load(f)
except Exception as e:
    print(f"Error reading {filepath}: {e}")
    exit(1)

total = len(data)
ok_cnt = sum(1 for r in data if r.get("status") == "ok")
timeout_cnt = sum(1 for r in data if r.get("status") == "timeout")
err_cnt = sum(1 for r in data if r.get("status") not in ("ok", "timeout"))

by_prob_arm = defaultdict(lambda: defaultdict(int))
for r in data:
    by_prob_arm[r["problem"]][r["arm"]] += 1

print("=" * 65)
print(f"STALL RELAXATION BENCHMARK STATUS: {total}/300 runs ({total/3.0:.1f}%)")
print(f"Status breakdown: OK={ok_cnt}, Timeouts={timeout_cnt}, Errors={err_cnt}")
print("=" * 65)

problems = ["parity4", "majority5", "parity5"]
arms = ["static_14", "static_100", "stall_relax_K3", "stall_relax_K5", "trigger_only_ctrl"]

print(f"{'Problem':<12} " + " ".join(f"{a[:10]:<10}" for a in arms) + f" {'Total':<6}")
print("-" * 65)
for p in problems:
    row = f"{p:<12} "
    p_tot = 0
    for a in arms:
        c = by_prob_arm[p][a]
        p_tot += c
        row += f"{c:>2}/20{'':<6} "
    row += f"{p_tot:>3}/100"
    print(row)
print("=" * 65)

if data:
    last = data[-1]
    if last.get("status") == "ok":
        print(f"Latest: {last['problem']} {last['arm']} s={last['seed']} -> Raw={last['best_raw']} Lits={last['literals']} Break={last['breakout']}")
    else:
        print(f"Latest: {last['problem']} {last['arm']} s={last['seed']} -> Status: {last['status']}")
