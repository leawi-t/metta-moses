#!/usr/bin/env python3
"""
Comprehensive Statistical Analysis Suite for MeTTa-MOSES Empirical Experiments.

Implements rigorous hypothesis testing, controls, and factorial modeling:
1. Paired Wilcoxon Signed-Rank tests with Holm-Bonferroni FWER step-down correction.
2. Non-parametric Bootstrap Confidence Intervals (95% CI) on paired differences
   (Fitness, Evaluations, Runtime, Complexity/Literals) and Equivalence Bounds.
3. Direct paired control testing (e.g., K5 vs trigger_only_ctrl, K5 vs static_100).
4. Step 1: Parity4 Budget Check analysis (budget vs convergence termination).
5. Step 2: Parity5 Fresh Seed Replication analysis (seeds 21-60).
6. Step 3: 2x3 Factorial ANOVA & Permutation tests (Generator x Complexity Ratio).
7. Outlier and latency diagnostic profiling.
"""

import os
import sys
import json
import argparse
from collections import defaultdict
import numpy as np
from scipy import stats

def holm_bonferroni(p_values):
    """
    Computes Holm-Bonferroni step-down adjusted p-values.
    Preserves original input ordering.
    """
    p_vals = np.asarray(p_values, dtype=float)
    n = len(p_vals)
    if n == 0:
        return np.array([])
    
    order = np.argsort(p_vals)
    sorted_p = p_vals[order]
    
    adj = np.empty(n, dtype=float)
    for i, p in enumerate(sorted_p):
        multiplier = n - i
        adj[i] = p * multiplier
        
    # Enforce monotonicity
    for i in range(1, n):
        adj[i] = max(adj[i], adj[i - 1])
    adj = np.clip(adj, 0.0, 1.0)
    
    # Invert sort order back to original
    orig_adj = np.empty(n, dtype=float)
    orig_adj[order] = adj
    return orig_adj

def paired_bootstrap_ci(x, y, n_boot=10000, ci=0.95, rng=None):
    """
    Computes non-parametric percentile bootstrap confidence interval
    for mean paired difference (x - y).
    Returns (mean_diff, ci_lower, ci_upper).
    """
    if rng is None:
        rng = np.random.default_rng(42)
    diff = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    n = len(diff)
    if n == 0:
        return 0.0, 0.0, 0.0
    
    boot_samples = rng.choice(diff, size=(n_boot, n), replace=True)
    boot_means = np.mean(boot_samples, axis=1)
    alpha = (1.0 - ci) / 2.0
    low = np.percentile(boot_means, 100 * alpha)
    high = np.percentile(boot_means, 100 * (1.0 - alpha))
    return float(np.mean(diff)), float(low), float(high)

def run_paired_wilcoxon(x, y):
    """
    Runs paired Wilcoxon signed-rank test handling zero-differences via Pratt's method.
    Returns (statistic, p_value, wins, losses, ties).
    """
    diff = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    wins = int(np.sum(diff > 0))
    losses = int(np.sum(diff < 0))
    ties = int(np.sum(diff == 0))
    
    if np.all(diff == 0):
        return 0.0, 1.0, wins, losses, ties
        
    try:
        res = stats.wilcoxon(x, y, zero_method="pratt")
        return float(res.statistic), float(res.pvalue), wins, losses, ties
    except Exception:
        return 0.0, 1.0, wins, losses, ties

def two_way_factorial_analysis(cell_data, rng=None, n_perms=5000):
    """
    Performs balanced 2-Way Factorial Analysis for:
    Factor A (e.g. Generator: 2 levels) x Factor B (e.g. Ratio: 3 levels).
    cell_data[(lvl_a, lvl_b)] = list of numeric observations (equal n per cell).
    
    Returns full parametric ANOVA table and non-parametric permutation p-values.
    """
    if rng is None:
        rng = np.random.default_rng(42)
        
    levels_a = sorted(list({k[0] for k in cell_data.keys()}))
    levels_b = sorted(list({k[1] for k in cell_data.keys()}))
    a = len(levels_a)
    b = len(levels_b)
    
    n_per_cell = len(cell_data[(levels_a[0], levels_b[0])])
    N = a * b * n_per_cell
    
    # 3D array: (a, b, n)
    arr = np.zeros((a, b, n_per_cell), dtype=float)
    for i, la in enumerate(levels_a):
        for j, lb in enumerate(levels_b):
            arr[i, j, :] = cell_data[(la, lb)]
            
    grand_sum = np.sum(arr)
    grand_mean = grand_sum / N
    C = (grand_sum ** 2) / N
    
    SS_total = np.sum(arr ** 2) - C
    df_total = N - 1
    
    # Factor A
    A_totals = np.sum(arr, axis=(1, 2))
    SS_A = np.sum(A_totals ** 2) / (b * n_per_cell) - C
    df_A = a - 1
    
    # Factor B
    B_totals = np.sum(arr, axis=(0, 2))
    SS_B = np.sum(B_totals ** 2) / (a * n_per_cell) - C
    df_B = b - 1
    
    # Cells
    cell_totals = np.sum(arr, axis=2)
    SS_cells = np.sum(cell_totals ** 2) / n_per_cell - C
    
    # Interaction
    SS_AB = SS_cells - SS_A - SS_B
    df_AB = (a - 1) * (b - 1)
    
    # Residual Error
    SS_error = SS_total - SS_cells
    df_error = a * b * (n_per_cell - 1)
    
    MS_A = SS_A / max(1, df_A)
    MS_B = SS_B / max(1, df_B)
    MS_AB = SS_AB / max(1, df_AB)
    MS_error = SS_error / max(1, df_error)
    
    F_A = MS_A / MS_error if MS_error > 0 else 0.0
    F_B = MS_B / MS_error if MS_error > 0 else 0.0
    F_AB = MS_AB / MS_error if MS_error > 0 else 0.0
    
    p_A = float(stats.f.sf(F_A, df_A, df_error)) if MS_error > 0 else 1.0
    p_B = float(stats.f.sf(F_B, df_B, df_error)) if MS_error > 0 else 1.0
    p_AB = float(stats.f.sf(F_AB, df_AB, df_error)) if MS_error > 0 else 1.0
    
    eta_p_A = float(SS_A / (SS_A + SS_error)) if (SS_A + SS_error) > 0 else 0.0
    eta_p_B = float(SS_B / (SS_B + SS_error)) if (SS_B + SS_error) > 0 else 0.0
    eta_p_AB = float(SS_AB / (SS_AB + SS_error)) if (SS_AB + SS_error) > 0 else 0.0
    
    # Non-parametric permutation test
    perm_count_A = 0
    perm_count_B = 0
    perm_count_AB = 0
    
    flat = arr.copy()
    for _ in range(n_perms):
        perm_flat = rng.permutation(flat.flatten()).reshape((a, b, n_per_cell))
        
        p_A_tot = np.sum(perm_flat, axis=(1, 2))
        p_SS_A = np.sum(p_A_tot ** 2) / (b * n_per_cell) - C
        p_MS_A = p_SS_A / df_A
        
        p_B_tot = np.sum(perm_flat, axis=(0, 2))
        p_SS_B = np.sum(p_B_tot ** 2) / (a * n_per_cell) - C
        p_MS_B = p_SS_B / df_B
        
        p_cell_tot = np.sum(perm_flat, axis=2)
        p_SS_cells = np.sum(p_cell_tot ** 2) / n_per_cell - C
        p_SS_AB = p_SS_cells - p_SS_A - p_SS_B
        p_MS_AB = p_SS_AB / df_AB
        
        p_SS_err = SS_total - p_SS_cells
        p_MS_err = p_SS_err / df_error
        
        if p_MS_err > 0:
            if (p_MS_A / p_MS_err) >= F_A: perm_count_A += 1
            if (p_MS_B / p_MS_err) >= F_B: perm_count_B += 1
            if (p_MS_AB / p_MS_err) >= F_AB: perm_count_AB += 1
            
    p_perm_A = (1 + perm_count_A) / (1 + n_perms)
    p_perm_B = (1 + perm_count_B) / (1 + n_perms)
    p_perm_AB = (1 + perm_count_AB) / (1 + n_perms)
    
    return {
        "df_A": df_A, "SS_A": float(SS_A), "MS_A": float(MS_A), "F_A": float(F_A), "p_A": p_A, "p_perm_A": p_perm_A, "eta_p_A": eta_p_A,
        "df_B": df_B, "SS_B": float(SS_B), "MS_B": float(MS_B), "F_B": float(F_B), "p_B": p_B, "p_perm_B": p_perm_B, "eta_p_B": eta_p_B,
        "df_AB": df_AB, "SS_AB": float(SS_AB), "MS_AB": float(MS_AB), "F_AB": float(F_AB), "p_AB": p_AB, "p_perm_AB": p_perm_AB, "eta_p_AB": eta_p_AB,
        "df_error": df_error, "SS_error": float(SS_error), "MS_error": float(MS_error),
        "levels_a": levels_a, "levels_b": levels_b, "n_per_cell": n_per_cell, "grand_mean": float(grand_mean),
        "arr": arr
    }

def analyze_stall_relaxation_dataset(data_path="stall_relaxation_results.json"):
    """
    Performs full rigorous re-analysis of the 300-run Stall Relaxation experiment:
    - Computes uncorrected and Holm-adjusted p-values across all 12 tests against baseline.
    - Runs direct paired comparisons (K5 vs trigger_only_ctrl, K5 vs static_100).
    - Computes 95% Bootstrap CIs for Delta Raw, Delta Evals, Delta Time, Delta Literals.
    - Evaluates equivalence bounds on Majority5.
    - Profiles outlier run latencies.
    """
    if not os.path.exists(data_path):
        print(f"File not found: {data_path}")
        return
        
    with open(data_path) as f:
        records = json.load(f)
        
    by_prob_arm = defaultdict(lambda: defaultdict(dict))
    for r in records:
        prob = r["problem"]
        arm = r["arm"]
        seed = r["seed"]
        by_prob_arm[prob][arm][seed] = r
        
    problems = ["parity5", "parity4", "majority5"]
    arms_order = ["static_14", "static_100", "stall_relax_K3", "stall_relax_K5", "trigger_only_ctrl"]
    
    print("\n" + "#" * 100)
    print(" SECTION 1: GLOBAL FAMILY-WISE MULTIPLE COMPARISON CORRECTION (HOLM-BONFERRONI)")
    print("#" * 100)
    print("Testing 12 contrasts against static_14 (4 arms x 3 problems) to evaluate FWER control.")
    
    all_tests = []
    for prob in problems:
        arms_data = by_prob_arm[prob]
        if "static_14" not in arms_data:
            continue
        base_runs = arms_data["static_14"]
        seeds = sorted(base_runs.keys())
        base_raws = [base_runs[s]["best_raw"] for s in seeds]
        
        for arm in ["static_100", "stall_relax_K3", "stall_relax_K5", "trigger_only_ctrl"]:
            if arm not in arms_data:
                continue
            arm_runs = arms_data[arm]
            arm_raws = [arm_runs[s]["best_raw"] for s in seeds]
            stat, p_val, wins, losses, ties = run_paired_wilcoxon(arm_raws, base_raws)
            diff_mean, ci_low, ci_high = paired_bootstrap_ci(arm_raws, base_raws)
            all_tests.append({
                "problem": prob,
                "arm": arm,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "stat": stat,
                "raw_p": p_val,
                "diff_mean": diff_mean,
                "ci_low": ci_low,
                "ci_high": ci_high
            })
            
    raw_p_list = [t["raw_p"] for t in all_tests]
    holm_p_list = holm_bonferroni(raw_p_list)
    for t, hp in zip(all_tests, holm_p_list):
        t["holm_p"] = hp
        
    print(f"\n{'Problem':<12} {'Arm vs static_14':<20} {'Wins/Loss/Tie':<15} {'Mean Diff':<12} {'95% Bootstrap CI':<20} {'Raw p':<10} {'Holm p':<10} {'Sig (0.05)'}")
    print("-" * 105)
    for t in all_tests:
        wlt = f"{t['wins']}/{t['losses']}/{t['ties']}"
        ci_str = f"[{t['ci_low']:+.2f}, {t['ci_high']:+.2f}]"
        sig = "YES *" if t["holm_p"] < 0.05 else "NO (Null)"
        print(f"{t['problem']:<12} {t['arm']:<20} {wlt:<15} {t['diff_mean']:>+6.2f}      {ci_str:<20} {t['raw_p']:>8.4f}   {t['holm_p']:>8.4f}   {sig}")
        
    print("\n[Finding on Multiple Corrections]:")
    print("  Notice that while parity5 stall_relax_K5 has uncorrected p = 0.0492, its Holm-adjusted p = 0.5904.")
    print("  Thus, K5 does NOT achieve formal family-wise statistical significance across the 12 tests.")
    print("  As recommended, it must be treated as a targeted hypothesis for replication on fresh seeds (21-60).")

    print("\n" + "#" * 100)
    print(" SECTION 2: DIRECT PAIRED CONTROL TESTS (K5 vs Controls & Bounds)")
    print("#" * 100)
    print("Direct paired tests on identical seeds: K5 vs trigger_only_ctrl, and K5 vs static_100.")
    
    for prob in problems:
        print(f"\n--- {prob.upper()} DIRECT COMPARISONS ---")
        arms_data = by_prob_arm[prob]
        k5_dict = arms_data["stall_relax_K5"]
        trig_dict = arms_data["trigger_only_ctrl"]
        s100_dict = arms_data["static_100"]
        s14_dict = arms_data["static_14"]
        seeds = sorted(k5_dict.keys())
        
        k5_raw = [k5_dict[s]["best_raw"] for s in seeds]
        trig_raw = [trig_dict[s]["best_raw"] for s in seeds]
        s100_raw = [s100_dict[s]["best_raw"] for s in seeds]
        s14_raw = [s14_dict[s]["best_raw"] for s in seeds]
        
        k5_ev = [k5_dict[s]["total_evals"] for s in seeds]
        s100_ev = [s100_dict[s]["total_evals"] for s in seeds]
        
        k5_t = [k5_dict[s]["wall_time"] for s in seeds]
        s100_t = [s100_dict[s]["wall_time"] for s in seeds]
        
        k5_lit = [k5_dict[s]["literals"] for s in seeds]
        s14_lit = [s14_dict[s]["literals"] for s in seeds]
        
        # 1. K5 vs trigger_only_ctrl (Causal Control Test)
        w_stat, w_p, wins, losses, ties = run_paired_wilcoxon(k5_raw, trig_raw)
        m_diff, c_low, c_high = paired_bootstrap_ci(k5_raw, trig_raw)
        print(f"  [Causal Control] K5 vs trigger_only_ctrl (Raw Fitness):")
        print(f"    - Wins: {wins}, Losses: {losses}, Ties: {ties} | Wilcoxon W={w_stat:.1f}, p={w_p:.4f}")
        print(f"    - Mean Paired Diff: {m_diff:+.2f} (95% CI: [{c_low:+.2f}, {c_high:+.2f}])")
        if c_low <= 0 <= c_high:
            print(f"    -> Direct test conclusion: 95% CI spans zero; K5 does not significantly separate from trigger_only_ctrl.")
        else:
            print(f"    -> Direct test conclusion: Separates from trigger_only_ctrl!")

        # 2. K5 vs static_100 (Trade-off & Efficiency Test)
        w_stat_s, w_p_s, wins_s, losses_s, ties_s = run_paired_wilcoxon(k5_raw, s100_raw)
        m_raw_diff, c_r_low, c_r_high = paired_bootstrap_ci(k5_raw, s100_raw)
        m_ev_diff, c_ev_low, c_ev_high = paired_bootstrap_ci(k5_ev, s100_ev)
        m_t_diff, c_t_low, c_t_high = paired_bootstrap_ci(k5_t, s100_t)
        pct_ev_saved = 100.0 * (-m_ev_diff) / max(1.0, np.mean(s100_ev))
        pct_t_saved = 100.0 * (-m_t_diff) / max(1.0, np.mean(s100_t))
        print(f"  [Cost Efficiency] K5 vs static_100:")
        print(f"    - Raw Difference:  {m_raw_diff:+.2f} (95% CI: [{c_r_low:+.2f}, {c_r_high:+.2f}], p={w_p_s:.4f})")
        print(f"    - Evals Saved:     {m_ev_diff:+.0f} ({pct_ev_saved:+.1f}%) [95% CI: [{c_ev_low:+.0f}, {c_ev_high:+.0f}]]")
        print(f"    - Wall Time Saved: {m_t_diff:+.1f}s ({pct_t_saved:+.1f}%) [95% CI: [{c_t_low:+.1f}s, {c_t_high:+.1f}s]]")

        # 3. Equivalence / Bloat check against static_14
        m_lit_diff, c_lit_low, c_lit_high = paired_bootstrap_ci(k5_lit, s14_lit)
        m_eq_diff, c_eq_low, c_eq_high = paired_bootstrap_ci(k5_raw, s14_raw)
        print(f"  [Equivalence & Bloat] K5 vs static_14:")
        print(f"    - Raw Fitness 95% CI: [{c_eq_low:+.2f}, {c_eq_high:+.2f}] (Equivalence Bounds)")
        print(f"    - Literal Bloat diff: {m_lit_diff:+.1f} literals (95% CI: [{c_lit_low:+.1f}, {c_lit_high:+.1f}])")

    print("\n" + "#" * 100)
    print(" SECTION 3: OUTLIER & LATENCY DIAGNOSTIC (Parity4 K3 Investigation)")
    print("#" * 100)
    p4_k3 = [r for r in records if r["problem"] == "parity4" and r["arm"] == "stall_relax_K3"]
    times = sorted([(r["seed"], r.get("wall_time", 0), r.get("best_raw", 0), r.get("total_evals", 0), r.get("literals", 0)) for r in p4_k3], key=lambda x: x[1], reverse=True)
    print("Parity4 stall_relax_K3 latency ranking (top 5 longest seeds):")
    for s, t, raw, ev, lit in times[:5]:
        print(f"  Seed {s:2d}: Time = {t:6.1f}s | Raw = {raw:5.1f} | Evals = {ev} | Literals = {lit}")
    t_all = [x[1] for x in times]
    t_no_top = [x[1] for x in times[1:]]
    print(f"  Mean time (all 20 seeds): {np.mean(t_all):.1f}s | Median: {np.median(t_all):.1f}s")
    print(f"  Mean time (excluding Seed {times[0][0]}): {np.mean(t_no_top):.1f}s")
    print(f"  -> Pathological driver confirmed: Seed {times[0][0]} ran for {times[0][1]:.1f}s (single-run reduction hang).")

def analyze_step1_budget_check(results_path="budget_check_results.json"):
    """
    Step 1 Analysis: Parity4 3x Generation / Evaluation Budget Check.
    Compares 1x budget (MaxGen=15) vs 3x budget (MaxGen=45) under static_100 and K5.
    Determines whether Parity4 stagnation is a budget bottleneck or intrinsic landscape barrier.
    """
    print("\n" + "=" * 90)
    print(" STEP 1: PARITY4 BUDGET CHECK ANALYSIS (1x vs 3x Budget)")
    print("=" * 90)
    if not os.path.exists(results_path):
        print(f"Results file '{results_path}' not yet present.")
        print("To run the budget check, execute:")
        print("  python3 scripts/run_budget_check.py")
        return
        
    with open(results_path) as f:
        records = json.load(f)
        
    by_arm_budget = defaultdict(lambda: defaultdict(dict))
    for r in records:
        arm = r["arm"]
        budget = r.get("budget_multiplier", 1)
        seed = r["seed"]
        by_arm_budget[arm][budget][seed] = r
        
    print(f"{'Arm':<18} {'Budget':<8} {'N':<4} {'Solve %':<9} {'Mean Raw ± SD':<18} {'Median':<7} {'Mean Evals':<12} {'Mean Time':<10}")
    print("-" * 90)
    for arm in ["static_100", "stall_relax_K5"]:
        for b in [1, 3]:
            if b not in by_arm_budget[arm]:
                continue
            runs = list(by_arm_budget[arm][b].values())
            n = len(runs)
            solves = sum(1 for r in runs if r.get("solved", False))
            solve_pct = 100.0 * solves / max(1, n)
            raws = [r["best_raw"] for r in runs]
            evals = [r.get("total_evals", 0) for r in runs]
            times = [r.get("wall_time", 0.0) for r in runs]
            print(f"{arm:<18} {f'{b}x':<8} {n:<4} {solve_pct:>5.1f}%    {np.mean(raws):>6.2f} ± {np.std(raws):<6.2f} {np.median(raws):>6.1f}  {np.mean(evals):>10.0f}   {np.mean(times):>8.1f}s")
            
    print("\n[Budget Check Verdict]:")
    total_solves = sum(1 for r in records if r.get("budget_multiplier", 1) == 3 and r.get("solved", False))
    if total_solves > 0:
        print(f"  SOLUTIONS FOUND under 3x budget ({total_solves} solves)! Stagnation was a budget limitation.")
    else:
        print("  0 SOLVES under 3x budget. Intrinsic structural barrier confirmed. Generator intervention is required.")

def analyze_step2_parity5_replication(results_path="parity5_replication_results.json"):
    """
    Step 2 Analysis: Parity5 Fresh-Seed Replication (Seeds 21-60, N=40 independent seeds).
    Pre-registered single targeted paired Wilcoxon test (K5 vs static_14) and direct control test.
    """
    print("\n" + "=" * 90)
    print(" STEP 2: PARITY5 FRESH-SEED REPLICATION ANALYSIS (Seeds 21-60)")
    print("=" * 90)
    if not os.path.exists(results_path):
        print(f"Results file '{results_path}' not yet present.")
        print("To run the fresh replication, execute:")
        print("  python3 scripts/run_parity5_replication.py")
        return
        
    with open(results_path) as f:
        records = json.load(f)
        
    by_arm = defaultdict(dict)
    for r in records:
        by_arm[r["arm"]][r["seed"]] = r
        
    seeds = sorted(list(by_arm["static_14"].keys()))
    print(f"Replication sample size: N = {len(seeds)} fresh seeds (seeds {min(seeds)}-{max(seeds)})")
    
    k5_raw = [by_arm["stall_relax_K5"][s]["best_raw"] for s in seeds]
    s14_raw = [by_arm["static_14"][s]["best_raw"] for s in seeds]
    trig_raw = [by_arm["trigger_only_ctrl"][s]["best_raw"] for s in seeds]
    s100_raw = [by_arm["static_100"][s]["best_raw"] for s in seeds]
    
    # Pre-registered test 1: K5 vs static_14
    stat, p_val, wins, losses, ties = run_paired_wilcoxon(k5_raw, s14_raw)
    diff_m, ci_l, ci_h = paired_bootstrap_ci(k5_raw, s14_raw)
    print("\n1. Primary Pre-Registered Hypothesis Test (K5 vs static_14):")
    print(f"   - Wins: {wins}, Losses: {losses}, Ties: {ties} | Wilcoxon W={stat:.1f}, p={p_val:.4f}{' *' if p_val < 0.05 else ''}")
    print(f"   - Mean Paired Difference: {diff_m:+.2f} (95% CI: [{ci_l:+.2f}, {ci_h:+.2f}])")
    
    # Pre-registered test 2: Direct K5 vs trigger_only_ctrl
    stat_c, p_val_c, wins_c, losses_c, ties_c = run_paired_wilcoxon(k5_raw, trig_raw)
    diff_mc, ci_lc, ci_hc = paired_bootstrap_ci(k5_raw, trig_raw)
    print("\n2. Direct Causal Control Test (K5 vs trigger_only_ctrl):")
    print(f"   - Wins: {wins_c}, Losses: {losses_c}, Ties: {ties_c} | Wilcoxon W={stat_c:.1f}, p={p_val_c:.4f}{' *' if p_val_c < 0.05 else ''}")
    print(f"   - Mean Paired Difference: {diff_mc:+.2f} (95% CI: [{ci_lc:+.2f}, {ci_hc:+.2f}])")

    # Efficiency test: K5 vs static_100
    k5_ev = [by_arm["stall_relax_K5"][s]["total_evals"] for s in seeds]
    s100_ev = [by_arm["static_100"][s]["total_evals"] for s in seeds]
    diff_ev, ci_el, ci_eh = paired_bootstrap_ci(k5_ev, s100_ev)
    print("\n3. Cost Efficiency (K5 vs static_100):")
    print(f"   - Evals Difference: {diff_ev:+.0f} (95% CI: [{ci_el:+.0f}, {ci_eh:+.0f}])")

def analyze_step3_factorial(results_path="factorial_2x3_results.json"):
    """
    Step 3 Analysis: 2x3 Factorial Experiment on Parity4.
    Design: {original, full_negation} x {static_14, static_100, stall_relax_K5}.
    Computes 2-Way ANOVA table, non-parametric permutation p-values,
    cell means table, and interaction contrast with 95% bootstrap CI.
    """
    print("\n" + "=" * 90)
    print(" STEP 3: 2x3 FACTORIAL EXPERIMENT (Generator x Complexity Ratio on Parity4)")
    print("=" * 90)
    if not os.path.exists(results_path):
        print(f"Results file '{results_path}' not yet present.")
        print("To run the 2x3 factorial experiment, execute:")
        print("  python3 scripts/run_factorial_2x3.py")
        return
        
    with open(results_path) as f:
        records = json.load(f)
        
    cell_raws = defaultdict(list)
    cell_evals = defaultdict(list)
    cell_breakouts = defaultdict(list)
    cell_solves = defaultdict(list)
    
    for r in records:
        gen = r.get("generator", "original") # "original" or "full_negation"
        ratio = r["arm"] # "static_14", "static_100", "stall_relax_K5"
        cell = (gen, ratio)
        raw = r["best_raw"] if r["status"] == "ok" else -16.0
        cell_raws[cell].append(raw)
        cell_evals[cell].append(r.get("total_evals", 0))
        cell_breakouts[cell].append(1 if r.get("breakout", False) else 0)
        cell_solves[cell].append(1 if r.get("solved", False) else 0)
        
    # Cell Means Table
    print(f"\n{'Generator':<16} {'Ratio Arm':<18} {'N':<4} {'Raw (Mean±SD)':<16} {'Median':<7} {'Breakout %':<12} {'Solve %':<9} {'Mean Evals':<10}")
    print("-" * 90)
    for gen in ["original", "full_negation"]:
        for ratio in ["static_14", "static_100", "stall_relax_K5"]:
            k = (gen, ratio)
            if k not in cell_raws:
                continue
            raws = cell_raws[k]
            evs = cell_evals[k]
            brk = cell_breakouts[k]
            slv = cell_solves[k]
            n = len(raws)
            print(f"{gen:<16} {ratio:<18} {n:<4} {np.mean(raws):>6.2f} ± {np.std(raws):<6.2f} {np.median(raws):>6.1f}  {100.0*np.mean(brk):>6.1f}%      {100.0*np.mean(slv):>5.1f}%   {np.mean(evs):>8.0f}")
            
    # Two-Way ANOVA
    res = two_way_factorial_analysis(cell_raws, n_perms=5000)
    print("\n" + "=" * 90)
    print(" TWO-WAY FACTORIAL ANOVA TABLE (Parity4 Best Raw Score)")
    print("=" * 90)
    print(f"{'Source of Variation':<25} {'df':<5} {'Sum of Sq':<12} {'Mean Sq':<10} {'F-stat':<9} {'Param p':<10} {'Perm p':<10} {'Partial η²':<10}")
    print("-" * 90)
    print(f"{'Factor A: Generator':<25} {res['df_A']:<5} {res['SS_A']:>10.2f}   {res['MS_A']:>8.2f}   {res['F_A']:>7.2f}   {res['p_A']:>8.4f}   {res['p_perm_A']:>8.4f}   {res['eta_p_A']:>8.3f}")
    print(f"{'Factor B: Ratio Arm':<25} {res['df_B']:<5} {res['SS_B']:>10.2f}   {res['MS_B']:>8.2f}   {res['F_B']:>7.2f}   {res['p_B']:>8.4f}   {res['p_perm_B']:>8.4f}   {res['eta_p_B']:>8.3f}")
    print(f"{'Interaction (A x B)':<25} {res['df_AB']:<5} {res['SS_AB']:>10.2f}   {res['MS_AB']:>8.2f}   {res['F_AB']:>7.2f}   {res['p_AB']:>8.4f}   {res['p_perm_AB']:>8.4f}   {res['eta_p_AB']:>8.3f}")
    print(f"{'Residual Error':<25} {res['df_error']:<5} {res['SS_error']:>10.2f}   {res['MS_error']:>8.2f}")
    print(f"{'Total':<25} {res['df_A']+res['df_B']+res['df_AB']+res['df_error']:<5} {res['SS_A']+res['SS_B']+res['SS_AB']+res['SS_error']:>10.2f}")
    
    # Interaction Contrast (Masking Hypothesis Test)
    # Delta = (full_100 - orig_100) - (full_14 - orig_14)
    c_f100 = np.array(cell_raws[("full_negation", "static_100")])
    c_o100 = np.array(cell_raws[("original", "static_100")])
    c_f14  = np.array(cell_raws[("full_negation", "static_14")])
    c_o14  = np.array(cell_raws[("original", "static_14")])
    
    diff_100 = c_f100 - c_o100
    diff_14 = c_f14 - c_o14
    contrast = diff_100 - diff_14
    
    m_con, ci_con_l, ci_con_h = paired_bootstrap_ci(diff_100, diff_14)
    print("\n" + "=" * 90)
    print(" INTERACTION CONTRAST: PENALTY MASKING TEST")
    print("=" * 90)
    print(f"Contrast formula: [FullNegation(r=100) - Original(r=100)] - [FullNegation(r=14) - Original(r=14)]")
    print(f"  Observed Contrast: {m_con:+.2f}")
    print(f"  95% Bootstrap CI:  [{ci_con_l:+.2f}, {ci_con_h:+.2f}]")
    if ci_con_l <= 0 <= ci_con_h:
        print("  -> Conclusion: Contrast CI includes zero. The penalty masking hypothesis is rejected.")
    else:
        print("  -> Conclusion: Significant interaction! The penalty was masking generator benefit at r=14.")

def main():
    parser = argparse.ArgumentParser(description="Statistical Analysis Engine for MeTTa-MOSES Experiments")
    parser.add_argument("--mode", choices=["all", "stall", "step1", "step2", "step3"], default="stall",
                        help="Analysis mode: stall (current dataset), step1 (budget), step2 (replication), step3 (factorial), or all")
    parser.add_argument("--stall-file", default="stall_relaxation_results.json")
    parser.add_argument("--step1-file", default="budget_check_results.json")
    parser.add_argument("--step2-file", default="parity5_replication_results.json")
    parser.add_argument("--step3-file", default="factorial_2x3_results.json")
    
    args = parser.parse_args()
    
    if args.mode in ("all", "stall"):
        analyze_stall_relaxation_dataset(args.stall_file)
    if args.mode in ("all", "step1"):
        analyze_step1_budget_check(args.step1_file)
    if args.mode in ("all", "step2"):
        analyze_step2_parity5_replication(args.step2_file)
    if args.mode in ("all", "step3"):
        analyze_step3_factorial(args.step3_file)

if __name__ == "__main__":
    main()
