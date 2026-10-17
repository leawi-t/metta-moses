import sys
import visited_tracker
import stall_controller

_best_raw_ever = -1e9
_expansion_count = 0
_raw_levels = {}
_total_culled = 0
_total_better_raw_worse_pen = 0
_per_gen_progression = []

# Distinct culled candidate tracking
_current_gen_candidates = []
_current_gen_metapop_trees = []
_distinct_culled_better_raw_keys = set()
_culled_better_raw_archive = {}

_termination_reason = "unknown"

def get_best_raw_ever():
    return _best_raw_ever

def set_termination_reason(reason):
    global _termination_reason
    _termination_reason = str(reason)
    return True

def get_termination_reason():
    return _termination_reason

def reset():
    global _best_raw_ever, _expansion_count, _raw_levels, _total_culled, _total_better_raw_worse_pen, _per_gen_progression
    global _current_gen_candidates, _current_gen_metapop_trees, _distinct_culled_better_raw_keys, _culled_better_raw_archive
    global _termination_reason
    _termination_reason = "unknown"
    _best_raw_ever = -1e9
    _expansion_count = 0
    _raw_levels = {}
    _total_culled = 0
    _total_better_raw_worse_pen = 0
    _per_gen_progression = []
    _current_gen_candidates = []
    _current_gen_metapop_trees = []
    _distinct_culled_better_raw_keys = set()
    _culled_better_raw_archive = {}
    visited_tracker.reset()
    stall_controller.reset_controller()
    return True



def register_deme_candidate(tree_str, raw, pen, cpxy):
    global _current_gen_candidates
    try:
        r = float(raw)
        p = float(pen)
        c = float(cpxy)
    except Exception:
        r, p, c = -1e9, -1e9, 0.0
    _current_gen_candidates.append((str(tree_str), r, p, c))
    return True

def register_metapop_exemplar(tree_str):
    global _current_gen_metapop_trees
    _current_gen_metapop_trees.append(str(tree_str))
    return True

def finalize_generation_stats(gen, best_raw, literals, best_pen):
    global _best_raw_ever, _raw_levels, _per_gen_progression
    global _current_gen_candidates, _current_gen_metapop_trees
    global _distinct_culled_better_raw_keys, _culled_better_raw_archive

    try:
        cur_raw = float(best_raw)
        lits = int(float(literals))
        b_pen = float(best_pen)
        g = int(gen)
    except Exception:
        cur_raw, lits, b_pen, g = -1e9, 0, -1e9, int(gen)

    # 1. Update best_raw_ever and milestone levels
    if cur_raw > _best_raw_ever:
        _best_raw_ever = cur_raw
        if cur_raw not in _raw_levels:
            _raw_levels[cur_raw] = _expansion_count

    # 2. Identify candidates culled in this generation (not present in final metapopulation)
    survivor_keys = {visited_tracker.get_canonical_key(t) for t in _current_gen_metapop_trees}
    culled_this_gen = 0
    for tree_str, r, p, c in _current_gen_candidates:
        ck = visited_tracker.get_canonical_key(tree_str)
        if ck not in survivor_keys:
            culled_this_gen += 1
            _distinct_culled_better_raw_keys.add(ck)
            if ck not in _culled_better_raw_archive:
                _culled_better_raw_archive[ck] = {
                    "tree": tree_str,
                    "raw": r,
                    "pen": p,
                    "complexity": c,
                    "gen": g
                }

    # 3. Record per-gen progression
    _per_gen_progression.append({
        "gen": g,
        "exp": _expansion_count,
        "best_raw": cur_raw,
        "literals": lits,
        "best_pen": b_pen,
        "culled_this_gen": culled_this_gen,
        "distinct_culled_total": len(_distinct_culled_better_raw_keys)
    })

    # 4. Print Step2-GenStats (with all requested columns + culling metrics + effective ratio + state) and Step2-BestRaw
    eff_ratio = stall_controller.get_current_ratio()
    stall_state = stall_controller._controller.state
    print(f"(Step2-GenStats Gen: {g} Exp: {_expansion_count} BestRaw: {cur_raw} Literals: {lits} BestPen: {b_pen} CulledThisGen: {culled_this_gen} DistinctCulledTotal: {len(_distinct_culled_better_raw_keys)} EffectiveRatio: {eff_ratio} StallState: {stall_state})", flush=True)
    print(f"(Step2-BestRaw Gen: {g} Exp: {_expansion_count} Ever: {_best_raw_ever} CurrentMetapop: {cur_raw})", flush=True)

    # 5. Clear per-generation buffers
    _current_gen_candidates = []
    _current_gen_metapop_trees = []
    return cur_raw

def get_distinct_culled_count():
    return len(_distinct_culled_better_raw_keys)

def get_culled_archive():
    return _culled_better_raw_archive

def log_exemplar(gen, tree_str, raw, pen):
    global _expansion_count
    _expansion_count += 1
    canon_key = visited_tracker.get_canonical_key(tree_str)
    visits = visited_tracker.get_visit_count(tree_str)
    is_repeated = visits > 1
    rep_flag = "TRUE" if is_repeated else "FALSE"
    print(f"(Step2-Exemplar Gen: {gen} Exp: {_expansion_count} Repeated: {rep_flag} Visits: {visits} Raw: {raw} Pen: {pen} CanonKey: {canon_key})", flush=True)
    return is_repeated

def log_metapop_best_raw(gen, current_max_raw):
    # Maintained for backward compatibility if called directly
    global _best_raw_ever, _raw_levels, _per_gen_progression
    try:
        cur = float(current_max_raw)
    except Exception:
        cur = -1e9
    if cur > _best_raw_ever:
        _best_raw_ever = cur
        if cur not in _raw_levels:
            _raw_levels[cur] = _expansion_count
    print(f"(Step2-BestRaw Gen: {gen} Exp: {_expansion_count} Ever: {_best_raw_ever} CurrentMetapop: {cur})", flush=True)
    return _best_raw_ever

def log_deme_culling(deme_id, better_raw_worse_pen_cnt, culled_cnt):
    global _total_culled, _total_better_raw_worse_pen
    try:
        b = int(better_raw_worse_pen_cnt)
        c = int(culled_cnt)
    except Exception:
        b, c = 0, 0
    _total_better_raw_worse_pen += b
    _total_culled += c
    print(f"(Step2-DemeCulling Deme: {deme_id} BetterRawWorsePen: {better_raw_worse_pen_cnt} Culled: {culled_cnt})", flush=True)
    return True

def log_summary():
    st = visited_tracker.stats()
    summ = stall_controller._controller.get_summary()
    levels_str = " ".join(f"{k}:{v}" for k, v in sorted(_raw_levels.items()))
    print(f"(Step2-Summary UniqueVisited: {st['unique_keys']} TotalExpansions: {st['total_visits']} FallbackCount: {st['fallback_count']} BestRaw: {_best_raw_ever} BetterRawWorsePen: {_total_better_raw_worse_pen} DistinctCulledBetterRaw: {len(_distinct_culled_better_raw_keys)} Culled: {_total_culled} RelaxedGens: {summ['total_relaxed_gens']} FractionRelaxed: {summ['fraction_relaxed']:.2f} SwitchCount: {summ['switch_count']} Termination: {_termination_reason} Levels: [{levels_str}])", flush=True)
    return True


