import json
import os
import sys
from collections import defaultdict
import numpy as np
from scipy import stats

def analyze(filepath="stall_relaxation_results.json"):
    if not os.path.exists(filepath):
        print(f"Results file {filepath} not found.")
        return
        
    with open(filepath) as f:
        data = json.load(f)
        
    print(f"Total records in {filepath}: {len(data)}")
    
    # Group by problem and arm
    by_prob_arm = defaultdict(lambda: defaultdict(list))
    for r in data:
        if r.get("status") in ("ok", "timeout"):
            prob = r["problem"]
            arm = r["arm"]
            by_prob_arm[prob][arm].append(r)
            
    arms_order = ["static_14", "static_100", "stall_relax_K3", "stall_relax_K5", "trigger_only_ctrl"]
    
    for prob, arms_data in sorted(by_prob_arm.items()):
        print("\n" + "=" * 90)
        print(f"PROBLEM: {prob.upper()}")
        print("=" * 90)
        
        # Header
        print(f"{'Arm':<18} {'N':<4} {'Raw (Mean±SD)':<16} {'Median':<7} {'Breakout %':<12} {'Solve %':<9} {'Literals':<10} {'Evals':<7} {'FracRel':<9} {'Time(s)':<8}")
        print("-" * 90)
        
        base_raws = {}
        base_breakouts = {}
        
        # Index baseline static_14 by seed for paired tests
        if "static_14" in arms_data:
            for r in arms_data["static_14"]:
                raw = r["best_raw"] if r["status"] == "ok" else (r.get("best_raw", -1e9) if r.get("best_raw", -1e9) > -1e8 else -16.0)
                base_raws[r["seed"]] = raw
                base_breakouts[r["seed"]] = r.get("breakout", False)
                
        for arm in arms_order:
            if arm not in arms_data:
                continue
            runs = arms_data[arm]
            n_total = len(runs)
            
            raws = []
            lits = []
            evals = []
            frac_rel = []
            times = []
            breakouts = []
            solves = []
            
            paired_base = []
            paired_arm = []
            mcnemar_pairs = []
            
            for r in sorted(runs, key=lambda x: x["seed"]):
                s = r["seed"]
                is_ok = (r["status"] == "ok")
                raw = r["best_raw"] if is_ok else -16.0
                raws.append(raw)
                
                if is_ok:
                    lits.append(r.get("literals", 0))
                    evals.append(r.get("total_evals", 0))
                    frac_rel.append(r.get("fraction_relaxed", 0.0))
                    times.append(r.get("wall_time", 0.0))
                    breakouts.append(r.get("breakout", False))
                    solves.append(r.get("solved", False))
                else:
                    breakouts.append(False)
                    solves.append(False)
                    
                if s in base_raws:
                    paired_base.append(base_raws[s])
                    paired_arm.append(raw)
                    mcnemar_pairs.append((base_breakouts[s], r.get("breakout", False)))
                    
            mean_raw = np.mean(raws)
            sd_raw = np.std(raws)
            med_raw = np.median(raws)
            break_pct = 100.0 * sum(breakouts) / max(1, n_total)
            solve_pct = 100.0 * sum(solves) / max(1, n_total)
            mean_lits = np.mean(lits) if lits else 0
            mean_evals = np.mean(evals) if evals else 0
            mean_frac = np.mean(frac_rel) if frac_rel else 0
            mean_time = np.mean(times) if times else 0
            
            print(f"{arm:<18} {n_total:<4} {mean_raw:>6.2f} ± {sd_raw:<6.2f} {med_raw:>6.1f}  {break_pct:>6.1f}%      {solve_pct:>5.1f}%   {mean_lits:>6.1f}     {mean_evals:>6.0f}  {mean_frac:>6.2f}    {mean_time:>6.1f}")
            
        # Statistical comparisons vs static_14
        print("\n  Statistical tests vs Baseline (static_14):")
        for arm in ["static_100", "stall_relax_K3", "stall_relax_K5", "trigger_only_ctrl"]:
            if arm not in arms_data or "static_14" not in arms_data:
                continue
                
            runs = {r["seed"]: r for r in arms_data[arm]}
            paired_b = []
            paired_a = []
            b_wins = 0
            a_wins = 0
            ties = 0
            
            for s, b_raw in base_raws.items():
                if s in runs:
                    r = runs[s]
                    a_raw = r["best_raw"] if r["status"] == "ok" else -16.0
                    paired_b.append(b_raw)
                    paired_a.append(a_raw)
                    if a_raw > b_raw:
                        a_wins += 1
                    elif b_raw > a_raw:
                        b_wins += 1
                    else:
                        ties += 1
                        
            p_val = 1.0
            stat = 0.0
            diffs = np.array(paired_a) - np.array(paired_b)
            if np.any(diffs != 0):
                try:
                    res = stats.wilcoxon(paired_a, paired_b, zero_method="pratt")
                    p_val = res.pvalue
                    stat = res.statistic
                except Exception:
                    p_val = 1.0
                    
            print(f"    - {arm:<18} vs static_14: Arm Wins={a_wins}, Base Wins={b_wins}, Ties={ties} | Wilcoxon W={stat:.1f}, p={p_val:.4f}{' *' if p_val < 0.05 else ''}")

if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "stall_relaxation_results.json"
    analyze(filepath)
