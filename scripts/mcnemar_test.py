import json
from collections import defaultdict
import numpy as np
from scipy import stats

with open("stall_relaxation_results.json") as f:
    data = json.load(f)

by_prob_arm = defaultdict(lambda: defaultdict(dict))
for r in data:
    by_prob_arm[r["problem"]][r["arm"]][r["seed"]] = r

print("=" * 70)
print("MCNEMAR EXACT TEST ON BREAKOUT RATES VS STATIC_14")
print("=" * 70)

for prob in ["parity4", "parity5", "majority5"]:
    print(f"\nPROBLEM: {prob.upper()}")
    base_dict = by_prob_arm[prob]["static_14"]
    for arm in ["static_100", "stall_relax_K3", "stall_relax_K5", "trigger_only_ctrl"]:
        arm_dict = by_prob_arm[prob][arm]
        # Contingency table:
        # b: base=0, arm=1 (discordant: arm broke out, base failed)
        # c: base=1, arm=0 (discordant: base broke out, arm failed)
        b = 0
        c = 0
        both = 0
        neither = 0
        for s in range(1, 21):
            base_b = base_dict[s]["breakout"]
            arm_b = arm_dict[s]["breakout"]
            if arm_b and not base_b:
                b += 1
            elif base_b and not arm_b:
                c += 1
            elif base_b and arm_b:
                both += 1
            else:
                neither += 1
                
        # Exact binomial test for McNemar with small N
        total_discordant = b + c
        if total_discordant > 0:
            # Two-sided exact binomial test with p=0.5
            p_val = stats.binomtest(b, total_discordant, 0.5, alternative="two-sided").pvalue
        else:
            p_val = 1.0
            
        print(f"  {arm:<18} vs static_14: Discordant(+{b} / -{c}), Both={both}, Neither={neither} | McNemar exact p={p_val:.4f}{' *' if p_val < 0.05 else ''}")
