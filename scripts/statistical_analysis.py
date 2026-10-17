#!/usr/bin/env python3
"""Statistical analysis for the metta-moses experiments (corrected version).

Design rules:
  * every comparison is paired BY SEED (explicit alignment, never by list position);
  * missing/timeout runs: --missing intersect (default, drops seeds absent from any compared arm and
    reports them) or impute (missing raw score = worst possible = -n_rows; sensitivity analysis);
  * the Holm family is stated explicitly; exploratory tests are labelled and not corrected;
  * no conclusion text is hard-coded: sentences are generated from the numbers;
  * Wilcoxon zero handling is a CLI option (default "wilcox" = scipy default); run `--mode stall`
    first and check it reproduces your earlier table before trusting the rest.
"""
import argparse
import json
import os
import warnings
from collections import defaultdict

import numpy as np
from scipy import stats

ROWS = {"parity3": 8, "parity4": 16, "parity5": 32, "majority5": 32, "majority7": 128, "mux6": 64}
ZM = "wilcox"
MISSING = "intersect"
EQUIV = 0.5
RNG = np.random.default_rng(42)


# ---------- statistics helpers ----------
def holm(p):
    p = np.asarray(p, float)
    n = len(p)
    if n == 0:
        return p
    o = np.argsort(p)
    adj = np.maximum.accumulate((n - np.arange(n)) * p[o])
    out = np.empty(n)
    out[o] = np.clip(adj, 0, 1)
    return out


def wilcoxon(d):
    d = np.asarray(d, float)
    if np.count_nonzero(d) == 0:
        return 0.0, 1.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = stats.wilcoxon(d, zero_method=ZM)
    return float(r.statistic), float(r.pvalue)


def boot_ci(d, n_boot=10000, ci=0.95):
    d = np.asarray(d, float)
    if len(d) == 0:
        return float("nan"), float("nan"), float("nan")
    m = RNG.choice(d, size=(n_boot, len(d)), replace=True).mean(axis=1)
    a = (1 - ci) / 2
    return float(d.mean()), float(np.percentile(m, 100 * a)), float(np.percentile(m, 100 * (1 - a)))


def hodges_lehmann(d):
    d = np.asarray(d, float)
    if len(d) == 0:
        return float("nan")
    return float(np.median([(d[i] + d[j]) / 2 for i in range(len(d)) for j in range(i, len(d))]))


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return float(c - h), float(c + h)


def mcnemar(a, b):
    """exact McNemar on paired booleans: returns (a_only, b_only, p)."""
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    x, y = int(np.sum(a & ~b)), int(np.sum(~a & b))
    p = 1.0 if x + y == 0 else float(stats.binomtest(min(x, y), x + y, 0.5).pvalue)
    return x, y, p


def paired(x, y):
    d = np.asarray(x, float) - np.asarray(y, float)
    W, p = wilcoxon(d)
    m, lo, hi = boot_ci(d)
    return {"n": len(d), "wins": int((d > 0).sum()), "losses": int((d < 0).sum()), "ties": int((d == 0).sum()),
            "W": W, "p": p, "mean": m, "lo": lo, "hi": hi, "hl": hodges_lehmann(d), "d": d}


def fmt(t):
    return (f"{t['wins']}W/{t['losses']}L/{t['ties']}T  mean {t['mean']:+.2f} [{t['lo']:+.2f},{t['hi']:+.2f}]  "
            f"HL {t['hl']:+.2f}  W={t['W']:.1f} p={t['p']:.4f}")


# ---------- data access ----------
def load(path):
    if not os.path.exists(path):
        print(f"  (missing file: {path})")
        return []
    with open(path) as f:
        return json.load(f)


def table(records, problem=None, budget=None, generator=None):
    """arm -> {seed: record}, ok rows only (last wins); also returns non-ok rows by arm."""
    ok, bad = defaultdict(dict), defaultdict(list)
    for r in records:
        if problem and r.get("problem") != problem:
            continue
        if budget is not None and r.get("budget_multiplier", 1) != budget:
            continue
        if generator is not None and r.get("generator", "original") != generator:
            continue
        if r.get("status") == "ok" and r.get("best_raw") is not None and not r.get("censored"):
            ok[r["arm"]][r["seed"]] = r
        else:
            bad[r["arm"]].append(r)
    return ok, bad


def seeds_for(tbl, arms, problem):
    sets = [set(tbl.get(a, {})) for a in arms]
    if not all(sets):
        return []
    return sorted(set.union(*sets) if MISSING == "impute" else set.intersection(*sets))


def vec(tbl, arm, seeds, metric, problem):
    out = []
    for s in seeds:
        r = tbl[arm].get(s)
        if r is None:
            if metric == "best_raw":
                out.append(-float(ROWS.get(problem, 16)))  # impute worst case
            else:
                out.append(np.nan)
        else:
            out.append(float(r[metric]))
    return np.array(out)


def raw_at_evals(run_record, target_evals, carry_forward=True):
    traj_evals = run_record.get("evals_trajectory", [])
    traj_raw = run_record.get("raw_trajectory", [])
    if not traj_evals or not traj_raw:
        return run_record.get("best_raw")
    if not carry_forward and traj_evals[-1] < target_evals:
        return np.nan
    val = traj_raw[0]
    for ev, r in zip(traj_evals, traj_raw):
        if ev <= target_evals:
            val = r
        else:
            break
    return val


def report_drop(tbl, bad, arms, seeds):
    for a in arms:
        miss = sorted((set(seeds) - set(tbl.get(a, {}))))
        nb = len(bad.get(a, []))
        if miss or nb:
            print(f"    note: {a}: {nb} non-ok rows; seeds missing in analysis set: {miss}")


def summary_row(tbl, arm, problem):
    runs = list(tbl[arm].values())
    raw = np.array([r["best_raw"] for r in runs])
    brk = int(sum(r.get("breakout", False) for r in runs))
    slv = int(sum(r.get("solved", False) for r in runs))
    n = len(runs)
    lo, hi = wilson(brk, n)
    return (f"{arm:<20} n={n:<3} raw {raw.mean():+7.2f} ±{raw.std(ddof=1) if n > 1 else 0:5.2f} "
            f"med {np.median(raw):+6.1f}  breakout {brk}/{n} [{lo:.2f},{hi:.2f}]  solved {slv}/{n}  "
            f"evals med {np.median([r['total_evals'] for r in runs]):.0f}  "
            f"time med {np.median([r['wall_time'] for r in runs]):.0f}s")


# ---------- modes ----------
def mode_stall(path):
    recs = load(path)
    problems = [p for p in ("parity5", "parity4", "majority5") if any(r.get("problem") == p for r in recs)]
    print("\n== A. Per-arm summary (check against your earlier table first) ==")
    tests = []
    for p in problems:
        tbl, bad = table(recs, p)
        print(f"\n{p}:")
        for arm in tbl:
            print("  " + summary_row(tbl, arm, p))
        for arm in ("static_100", "stall_relax_K3", "stall_relax_K5", "trigger_only_ctrl"):
            if arm in tbl and "static_14" in tbl:
                s = seeds_for(tbl, [arm, "static_14"], p)
                t = paired(vec(tbl, arm, s, "best_raw", p), vec(tbl, "static_14", s, "best_raw", p))
                tests.append((p, arm, s, t))
    print("\n== B. Confirmatory family: 12 raw-score contrasts vs static_14, Holm-corrected ==")
    adj = holm([t["p"] for _, _, _, t in tests])
    for (p, arm, s, t), h in zip(tests, adj):
        print(f"  {p:<10} {arm:<18} n={t['n']:<3} {fmt(t)}  Holm p={h:.4f}  "
              f"{'significant' if h < 0.05 else 'not significant'}")
    print("\n== C. Exploratory (uncorrected, label as exploratory) ==")
    for p in problems:
        tbl, bad = table(recs, p)
        if all(a in tbl for a in ("stall_relax_K5", "trigger_only_ctrl")):
            s = seeds_for(tbl, ["stall_relax_K5", "trigger_only_ctrl"], p)
            print(f"  {p} K5 vs trigger_only_ctrl (raw): {fmt(paired(vec(tbl,'stall_relax_K5',s,'best_raw',p), vec(tbl,'trigger_only_ctrl',s,'best_raw',p)))}")
        if all(a in tbl for a in ("stall_relax_K5", "static_100")):
            s = seeds_for(tbl, ["stall_relax_K5", "static_100"], p)
            ev = paired(vec(tbl, "stall_relax_K5", s, "total_evals", p), vec(tbl, "static_100", s, "total_evals", p))
            tm = vec(tbl, "stall_relax_K5", s, "wall_time", p) / vec(tbl, "static_100", s, "wall_time", p)
            print(f"  {p} K5 vs static_100 (raw): {fmt(paired(vec(tbl,'stall_relax_K5',s,'best_raw',p), vec(tbl,'static_100',s,'best_raw',p)))}")
            print(f"      evals diff mean {ev['mean']:+.0f} [{ev['lo']:+.0f},{ev['hi']:+.0f}]; median time ratio {np.nanmedian(tm):.2f}")
        if all(a in tbl for a in ("stall_relax_K5", "static_14")):
            s = seeds_for(tbl, ["stall_relax_K5", "static_14"], p)
            a_, b_, pm = mcnemar(vec(tbl, "stall_relax_K5", s, "breakout", p), vec(tbl, "static_14", s, "breakout", p))
            print(f"  {p} breakout K5-only {a_}, static_14-only {b_}, exact McNemar p={pm:.4f}")
    print(f"\n== D. Equivalence check on majority5 (margin ±{EQUIV} raw): CI inside margin => equivalent ==")
    tbl, _ = table(recs, "majority5")
    for arm in ("static_100", "stall_relax_K3", "stall_relax_K5", "trigger_only_ctrl"):
        if arm in tbl and "static_14" in tbl:
            s = seeds_for(tbl, [arm, "static_14"], "majority5")
            t = paired(vec(tbl, arm, s, "best_raw", "majority5"), vec(tbl, "static_14", s, "best_raw", "majority5"))
            print(f"  {arm:<18} CI [{t['lo']:+.2f},{t['hi']:+.2f}] -> "
                  f"{'within margin' if -EQUIV <= t['lo'] and t['hi'] <= EQUIV else 'not shown equivalent'}")
    print("\n== E. Slowest runs per arm (diagnostic only; inspect logs before explaining them) ==")
    for p in problems:
        tbl, _ = table(recs, p)
        for arm in tbl:
            top = sorted(tbl[arm].values(), key=lambda r: -r["wall_time"])[:3]
            tt = np.array([r["wall_time"] for r in tbl[arm].values()])
            print(f"  {p} {arm}: median {np.median(tt):.0f}s, max {tt.max():.0f}s; slowest seeds "
                  + ", ".join(f"{r['seed']}({r['wall_time']:.0f}s, evals {r['total_evals']})" for r in top))


def mode_step1(path):
    recs = load(path)
    probs = {r.get("problem") for r in recs if r.get("problem")}
    prob = probs.pop() if len(probs) == 1 else "parity4"
    tbl1, bad1 = table(recs, prob, budget=1)
    tbl3, bad3 = table(recs, prob, budget=3)
    arms = sorted(set(tbl1) | set(tbl3))
    print(f"\n== Budget check on {prob} ==")
    for arm in arms:
        for lab, t, b in (("1x", tbl1, bad1), ("3x", tbl3, bad3)):
            if arm in t:
                print(f"  {lab} " + summary_row(t, arm, prob))
                term = defaultdict(int)
                for r in t[arm].values():
                    term[r.get("termination", "unknown")] += 1
                nb = len(b.get(arm, []))
                print(f"      termination: {dict(term)}; non-ok/censored rows: {nb}")
        if arm in tbl1 and arm in tbl3:
            s = sorted(set(tbl1[arm]) & set(tbl3[arm]))
            t = paired(vec(tbl3, arm, s, "best_raw", prob), vec(tbl1, arm, s, "best_raw", prob))
            print(f"      3x vs 1x paired raw (n={len(s)}): {fmt(t)}")
    solved3 = sum(r.get("solved", False) for a in tbl3 for r in tbl3[a].values())
    n3 = sum(len(tbl3[a]) for a in tbl3)
    if n3 == 0:
        print("  no 3x rows yet")
        return
    lo, hi = wilson(solved3, n3)
    print(f"\n  3x solves: {solved3}/{n3} (Wilson 95% CI [{lo:.2f},{hi:.2f}]). With ~10 seeds per arm this "
          f"bounds the solve rate only loosely; compare raw-score trajectories, not just solves.")
    mg = [r.get("termination") for a in tbl3 for r in tbl3[a].values()]
    print(f"  Runs ending at the generation cap: {mg.count('max_gen_reached')}/{len(mg)}")


def mode_step2(path):
    recs = load(path)
    p = "parity5"
    tbl, bad = table(recs, p)
    print("\n== Step 2: parity5 replication (seeds 21-60) ==")
    for arm in tbl:
        print("  " + summary_row(tbl, arm, p))
    ctrl = "trigger_only_K5" if "trigger_only_K5" in tbl else "trigger_only_ctrl"
    if ctrl != "trigger_only_K5":
        print("  WARNING: matched control trigger_only_K5 missing; trigger_only_ctrl uses K=3 (confounded).")
    fam = []
    for a, b in (("stall_relax_K5", "static_14"), ("stall_relax_K5", ctrl)):
        if a in tbl and b in tbl:
            s = seeds_for(tbl, [a, b], p)
            report_drop(tbl, bad, [a, b], s)
            fam.append((a, b, paired(vec(tbl, a, s, "best_raw", p), vec(tbl, b, s, "best_raw", p))))
    print("\n  Confirmatory family (2 tests, Holm):")
    adj = holm([t["p"] for _, _, t in fam])
    for (a, b, t), h in zip(fam, adj):
        print(f"    {a} vs {b} n={t['n']}: {fmt(t)}  Holm p={h:.4f}")
    print("\n  Exploratory:")
    for a, b in (("static_100", "static_14"), ("stall_relax_K5", "static_100")):
        if a in tbl and b in tbl:
            s = seeds_for(tbl, [a, b], p)
            print(f"    {a} vs {b} raw: {fmt(paired(vec(tbl,a,s,'best_raw',p), vec(tbl,b,s,'best_raw',p)))}")
            ev = paired(vec(tbl, a, s, "total_evals", p), vec(tbl, b, s, "total_evals", p))
            print(f"      evals diff {ev['mean']:+.0f} [{ev['lo']:+.0f},{ev['hi']:+.0f}]")
    if "stall_relax_K5" in tbl and "static_14" in tbl:
        s = seeds_for(tbl, ["stall_relax_K5", "static_14"], p)
        x, y, pm = mcnemar(vec(tbl, "stall_relax_K5", s, "breakout", p), vec(tbl, "static_14", s, "breakout", p))
        print(f"    breakout K5-only {x}, static_14-only {y}, exact McNemar p={pm:.4f}")

    has_trajectories = any(r.get("evals_trajectory") for a in tbl for r in tbl[a].values())
    if has_trajectories:
        print("\n  Trajectory comparison at equal evaluations (Exploratory):")
        print("    Policy: Stated comparison at checkpoints reached by majority of runs (>=90% active at <=2000 evals).")
        eval_milestones = [1000, 1500, 2000, 2500]
        for e_target in eval_milestones:
            print(f"\n    At {e_target} cumulative evaluations:")
            counts = {arm: sum(r.get("total_evals", 0) >= e_target for r in tbl[arm].values()) for arm in tbl}
            print("      Active runs reaching checkpoint: " + ", ".join(f"{arm}={counts[arm]}/{len(tbl[arm])}" for arm in tbl))
            for arm in tbl:
                vals = [raw_at_evals(r, e_target, carry_forward=True) for r in tbl[arm].values()]
                print(f"      {arm:<20} mean {np.mean(vals):+6.2f}  med {np.median(vals):+5.1f}")
            for a, b in (("stall_relax_K5", "static_14"), ("stall_relax_K5", "static_100")):
                if a in tbl and b in tbl:
                    s = seeds_for(tbl, [a, b], p)
                    # 1. Carried-forward (terminal raw carried forward for finished runs)
                    va_c = np.array([raw_at_evals(tbl[a][seed], e_target, carry_forward=True) for seed in s])
                    vb_c = np.array([raw_at_evals(tbl[b][seed], e_target, carry_forward=True) for seed in s])
                    t_c = paired(va_c, vb_c)
                    # 2. Active-only (both runs reached checkpoint)
                    va_act = np.array([raw_at_evals(tbl[a][seed], e_target, carry_forward=False) for seed in s])
                    vb_act = np.array([raw_at_evals(tbl[b][seed], e_target, carry_forward=False) for seed in s])
                    valid = ~(np.isnan(va_act) | np.isnan(vb_act))
                    t_act = paired(va_act[valid], vb_act[valid]) if np.sum(valid) >= 5 else None
                    act_str = f" [active-only n={int(np.sum(valid))}: {fmt(t_act)}]" if t_act else ""
                    print(f"      {a} vs {b}: {fmt(t_c)}{act_str}")


def mode_step3(path):
    recs = load(path)
    gens = ("original", "full_negation")
    p = "parity4"
    available_arms = sorted({r["arm"] for r in recs if r.get("problem") == p and r.get("status") == "ok"})
    candidate_arms = [a for a in ("static_100", "stall_relax_K5", "static_14") if a in available_arms]
    if len(candidate_arms) < 2:
        print("\n== Step 3: factorial == (insufficient arms; need at least 2 arms)")
        return
    arms = tuple(candidate_arms)
    tbls = {}
    bads = {}
    for g in gens:
        tbls[g], bads[g] = table(recs, p, generator=g)
    sets = [set(tbls[g].get(a, {})) for g in gens for a in arms]
    if not all(sets):
        print(f"\n== Step 3: factorial == (cells missing among {gens} x {arms}; nothing to analyze yet)")
        return
    seeds = sorted(set.union(*sets) if MISSING == "impute" else set.intersection(*sets))
    print(f"\n== Step 3: 2x{len(arms)} factorial on parity4, {len(seeds)} seeds common to all cells ==")
    V = {(g, a): vec(tbls[g], a, seeds, "best_raw", p) for g in gens for a in arms}
    for g in gens:
        for a in arms:
            v = V[(g, a)]
            print(f"  {g:<14} {a:<16} mean {v.mean():+.2f} ±{v.std(ddof=1) if len(v)>1 else 0:.2f} median {np.median(v):+.1f}")
    d = {a: V[("full_negation", a)] - V[("original", a)] for a in arms}
    print(f"\n  Generator effect (full_negation - original) per ratio arm, Holm over {len(arms)}:")
    res = [(a, paired(V[("full_negation", a)], V[("original", a)])) for a in arms]
    for (a, t), h in zip(res, holm([t["p"] for _, t in res])):
        print(f"    {a:<16} {fmt(t)}  Holm p={h:.4f}")
    avg = np.mean([d[a] for a in arms], axis=0)
    W, pw = wilcoxon(avg)
    m, lo, hi = boot_ci(avg)
    print(f"  Generator main effect (mean over arms): {m:+.2f} [{lo:+.2f},{hi:+.2f}] W={W:.1f} p={pw:.4f}")
    print("\n  Interaction (does the generator effect depend on the ratio arm?):")
    if len(arms) == 2:
        diff_inter = d[arms[0]] - d[arms[1]]
        Wi, pi = wilcoxon(diff_inter)
        mi, loi, hii = boot_ci(diff_inter)
        print(f"    Interaction contrast ({arms[0]} - {arms[1]}): {mi:+.2f} [{loi:+.2f},{hii:+.2f}] W={Wi:.1f} p={pi:.4f}")
    else:
        fr = stats.friedmanchisquare(*[d[a] for a in arms])
        print(f"    Friedman test on per-seed generator effects across arms: chi2={fr.statistic:.2f} p={fr.pvalue:.4f}")
        cons = [("static_100 vs static_14", d["static_100"] - d["static_14"]),
                ("stall_relax_K5 vs static_14", d["stall_relax_K5"] - d["static_14"])]
        out = []
        for lab, c in cons:
            W, pc = wilcoxon(c)
            out.append((lab, boot_ci(c), pc))
        for (lab, ci, pc), h in zip(out, holm([o[2] for o in out])):
            print(f"    contrast {lab}: {ci[0]:+.2f} [{ci[1]:+.2f},{ci[2]:+.2f}] p={pc:.4f} Holm p={h:.4f}")
    print(f"\n  Ratio effect (mean over generators), Holm over {len(arms)*(len(arms)-1)//2}:")
    M = {a: np.mean([V[(g, a)] for g in gens], axis=0) for a in arms}
    pairs = [(arms[i], arms[j]) for i in range(len(arms)) for j in range(i+1, len(arms))]
    rr = [(a, b, paired(M[a], M[b])) for a, b in pairs]
    for (a, b, t), h in zip(rr, holm([t["p"] for _, _, t in rr])):
        print(f"    {a} vs {b}: {fmt(t)}  Holm p={h:.4f}")
    print("\n  Interpret absence of a significant interaction as 'not detected at this sample size', not 'rejected'.")


def mode_noisy(path):
    recs = load(path)
    if not recs:
        print(f"No records found in {path}")
        return
    noise_rates = sorted(list({r.get("noise_rate", 0.10) for r in recs}))
    for nr in noise_rates:
        sub = [r for r in recs if r.get("noise_rate", 0.10) == nr and (r.get("status") == "ok" or r.get("test_raw") is not None)]
        arms = sorted(list({r["arm"] for r in sub}))
        print(f"\n== Noisy Benchmark on Majority5 ({int(nr*100)}% label noise, {len(sub)} runs) ==")

        tbl = defaultdict(dict)
        for r in sub:
            tbl[r["arm"]][r["seed"]] = r

        print(f"\n  {'Arm':<22} {'N':<3} {'TrainRaw':<16} {'TestRaw':<16} {'TestErr':<14} {'Solves(Clean)':<16} {'Lits':<14} {'Time':<6}")
        print("  " + "-" * 110)
        for arm in arms:
            seeds = sorted(tbl[arm].keys())
            n = len(seeds)
            if n == 0:
                continue
            tr_raw = np.array([tbl[arm][s]["train_raw"] for s in seeds if tbl[arm][s].get("train_raw") is not None])
            ts_raw = np.array([tbl[arm][s]["test_raw"] for s in seeds if tbl[arm][s].get("test_raw") is not None])
            ts_err = np.array([tbl[arm][s]["test_error"] for s in seeds if tbl[arm][s].get("test_error") is not None])
            lits = np.array([tbl[arm][s]["literals"] for s in seeds if tbl[arm][s].get("literals") is not None])
            slv = sum(bool(tbl[arm][s].get("test_perfect")) for s in seeds)
            times = np.array([tbl[arm][s].get("wall_time", 0) for s in seeds])
            lo, hi = wilson(slv, n)
            print(f"  {arm:<22} n={n:<2} {tr_raw.mean():+5.2f}±{tr_raw.std(ddof=1) if n>1 else 0:4.2f} (med {np.median(tr_raw):+4.1f}) "
                  f"{ts_raw.mean():+5.2f}±{ts_raw.std(ddof=1) if n>1 else 0:4.2f} "
                  f"{ts_err.mean():4.2f}±{ts_err.std(ddof=1) if n>1 else 0:4.2f} (med {np.median(ts_err):3.1f}) "
                  f"{slv}/{n} [{lo:.2f},{hi:.2f}] "
                  f"{lits.mean():4.1f}±{lits.std(ddof=1) if n>1 else 0:4.1f} (med {np.median(lits):3.1f}) "
                  f"{np.median(times):4.0f}s")

        print("\n  Paired Differences on Clean Ground-Truth Test Raw (Holm-corrected across key contrasts):")
        contrasts = [
            ("stall_relax_K5", "static_14"),
            ("static_100", "static_14"),
            ("stall_relax_K5", "static_100"),
            ("static_100_rerank14", "static_100"),
        ]
        test_res = []
        for a, b in contrasts:
            if a in tbl and b in tbl:
                common = sorted([s for s in (set(tbl[a].keys()) & set(tbl[b].keys()))
                                 if tbl[a][s].get("test_raw") is not None and tbl[b][s].get("test_raw") is not None])
                if len(common) >= 3:
                    va = np.array([float(tbl[a][s]["test_raw"]) for s in common])
                    vb = np.array([float(tbl[b][s]["test_raw"]) for s in common])
                    test_res.append((a, b, common, paired(va, vb)))
        if test_res:
            pvals = [t["p"] for _, _, _, t in test_res]
            adjs = holm(pvals)
            for (a, b, comm, t), h in zip(test_res, adjs):
                print(f"    {a} vs {b} (n={len(comm)}): {fmt(t)}  Holm p={h:.4f}")

        print("\n  Paired Differences on Literals / Code Bloat:")
        for a, b in contrasts:
            if a in tbl and b in tbl:
                common = sorted([s for s in (set(tbl[a].keys()) & set(tbl[b].keys()))
                                 if tbl[a][s].get("literals") is not None and tbl[b][s].get("literals") is not None])
                if len(common) >= 3:
                    va = np.array([float(tbl[a][s]["literals"]) for s in common])
                    vb = np.array([float(tbl[b][s]["literals"]) for s in common])
                    t = paired(va, vb)
                    print(f"    {a} vs {b} (n={len(comm)}): {fmt(t)}")


def selftest():
    p = [0.01, 0.04, 0.03, 0.5, 0.002]
    try:
        from statsmodels.stats.multitest import multipletests
        ref = multipletests(p, method="holm")[1]
        assert np.allclose(holm(p), ref), (holm(p), ref)
        print("holm: matches statsmodels")
    except ImportError:
        print("holm:", holm(p), "(statsmodels not installed; expected [0.04 0.09 0.09 0.5 0.01])")
    assert abs(sum(wilson(5, 10)) / 2 - 0.5) < 1e-9
    print("wilson ok; mcnemar", mcnemar([1, 1, 0, 0], [0, 0, 1, 1]))


def main():
    global ZM, MISSING, EQUIV
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["stall", "step1", "step2", "step3", "noisy", "all", "selftest"], default="stall")
    ap.add_argument("--stall-file", default="stall_relaxation_results.json")
    ap.add_argument("--step1-file", default="budget_check_results.json")
    ap.add_argument("--step2-file", default="parity5_replication_results.json")
    ap.add_argument("--step3-file", default="factorial_2x3_results.json")
    ap.add_argument("--noisy-file", default="noisy_benchmark_results.json")
    ap.add_argument("--zero-method", default="pratt", choices=["wilcox", "pratt", "zsplit"])

    ap.add_argument("--missing", default="intersect", choices=["intersect", "impute"])
    ap.add_argument("--equiv-margin", type=float, default=0.5)
    a = ap.parse_args()
    ZM, MISSING, EQUIV = a.zero_method, a.missing, a.equiv_margin
    if a.mode == "selftest":
        return selftest()
    if a.mode in ("stall", "all"):
        mode_stall(a.stall_file)
    if a.mode in ("step1", "all"):
        mode_step1(a.step1_file)
    if a.mode in ("step2", "all"):
        mode_step2(a.step2_file)
    if a.mode in ("step3", "all"):
        mode_step3(a.step3_file)
    if a.mode in ("noisy", "all"):
        mode_noisy(a.noisy_file)


if __name__ == "__main__":
    main()