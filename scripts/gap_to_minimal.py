import json
import sys
import os
import sympy
from sympy.logic.boolalg import And, Or, Not, simplify_logic
from sympy import symbols
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import visited_tracker

def sexpr_to_sympy(sexpr):
    if isinstance(sexpr, str):
        s_low = sexpr.lower()
        if s_low in ('true', '1'):
            return sympy.true
        if s_low in ('false', '0'):
            return sympy.false
        return symbols(sexpr)
    if isinstance(sexpr, (list, tuple)):
        if not sexpr:
            return sympy.false
        op = sexpr[0]
        args = [sexpr_to_sympy(a) for a in sexpr[1:]]
        if op == 'AND':
            return And(*args)
        elif op == 'OR':
            return Or(*args)
        elif op == 'NOT':
            return Not(args[0])
    raise ValueError(f"Unknown sexpr: {sexpr}")

def count_literals(expr):
    if expr in (sympy.true, sympy.false):
        return 0
    if isinstance(expr, sympy.Symbol):
        return 1
    if isinstance(expr, sympy.Not):
        return count_literals(expr.args[0])
    if isinstance(expr, (sympy.And, sympy.Or)):
        return sum(count_literals(a) for a in expr.args)
    return 1

def count_tree_literals(parsed):
    if isinstance(parsed, str):
        return 0 if parsed.lower() in ('true', 'false') else 1
    return sum(count_tree_literals(c) for c in parsed[1:])

def run_analysis():
    files = ['sweep_p4_m5.json', 'step2_sweep_results.json', 'long_horizon_visited_stats.json']
    trees = set()
    for fname in files:
        if os.path.exists(fname):
            try:
                data = json.load(open(fname))
                for r in data:
                    for t in r.get('selected_trees', []):
                        if t not in ['true', 'FALSE', 'TRUE', 'false']:
                            trees.add(t)
            except Exception:
                pass

    print(f"Loaded {len(trees)} unique candidate trees across run logs.")
    gaps = []
    results = []

    for t_str in sorted(trees):
        try:
            parsed = visited_tracker.parse_sexpr(t_str)
            moses_lits = count_tree_literals(parsed)
            sym_expr = sexpr_to_sympy(parsed)
            
            # Compute minimal logic form offline
            min_dnf = simplify_logic(sym_expr, form='dnf', force=True)
            min_lits = count_literals(min_dnf)
            
            gap = (moses_lits - min_lits) / moses_lits if moses_lits > 0 else 0.0
            gaps.append(gap)
            results.append((moses_lits, min_lits, gap, t_str))
        except Exception as e:
            pass

    if not gaps:
        print("No trees could be analyzed.")
        return

    print("\n" + "="*70)
    print("GAP-TO-MINIMAL REDUCTION QUALITY ANALYSIS")
    print("="*70)
    print(f"Total trees evaluated:     {len(gaps)}")
    print(f"Mean MOSES literals:       {np.mean([r[0] for r in results]):.2f}")
    print(f"Mean Minimal literals:     {np.mean([r[1] for r in results]):.2f}")
    print(f"Mean Gap to Minimal:       {np.mean(gaps)*100:.2f}%")
    print(f"Median Gap to Minimal:     {np.median(gaps)*100:.2f}%")
    print(f"Max Gap:                   {np.max(gaps)*100:.2f}%")
    print(f"Min Gap:                   {np.min(gaps)*100:.2f}%")
    print(f"Fraction with Gap > 0:     {sum(g > 0 for g in gaps)/len(gaps)*100:.1f}%")
    print(f"Fraction with Gap >= 20%:  {sum(g >= 0.20 for g in gaps)/len(gaps)*100:.1f}%")

    results.sort(key=lambda x: x[2], reverse=True)
    print("\nTop 5 Largest Reduction Gaps:")
    print("-" * 70)
    for m, mn, g, t in results[:5]:
        print(f"MOSES: {m} lits  ->  Minimal: {mn} lits  (Gap: {g*100:.1f}%):")
        print(f"  Tree: {t}")
        print()

    print("\nDistribution of Gaps:")
    print(f"  Gap == 0%   (optimal):       {sum(g == 0 for g in gaps)} ({sum(g == 0 for g in gaps)/len(gaps)*100:.1f}%)")
    print(f"  0% < Gap < 20%:              {sum(0 < g < 0.20 for g in gaps)} ({sum(0 < g < 0.20 for g in gaps)/len(gaps)*100:.1f}%)")
    print(f"  20% <= Gap < 50%:            {sum(0.20 <= g < 0.50 for g in gaps)} ({sum(0.20 <= g < 0.50 for g in gaps)/len(gaps)*100:.1f}%)")
    print(f"  Gap >= 50%:                  {sum(g >= 0.50 for g in gaps)} ({sum(g >= 0.50 for g in gaps)/len(gaps)*100:.1f}%)")

if __name__ == "__main__":
    run_analysis()
