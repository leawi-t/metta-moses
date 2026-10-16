import random
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import visited_tracker
except ImportError:
    from scripts import visited_tracker

VARS = ["X1", "X2", "X3", "X4", "X5"]

_tests_run = 0
_semantic_failures = []
_idempotence_failures = []
_permutation_failures = []

def eval_tree(parsed, env):
    if isinstance(parsed, str):
        p_up = parsed.upper()
        if p_up in ('TRUE', '1'):
            return True
        if p_up in ('FALSE', '0'):
            return False
        return env.get(parsed, False)
    if not parsed:
        return False
    op = parsed[0]
    if op == 'AND':
        return all(eval_tree(c, env) for c in parsed[1:])
    elif op == 'OR':
        return any(eval_tree(c, env) for c in parsed[1:])
    elif op == 'NOT':
        return not eval_tree(parsed[1], env)
    raise ValueError(f"Unknown op {op}")

def normalize_to_parsed(tree_input):
    if isinstance(tree_input, (list, tuple)):
        return [normalize_to_parsed(c) for c in tree_input]
    if isinstance(tree_input, str):
        s = tree_input.strip()
        if s.startswith('[') and s.endswith(']'):
            import ast
            try:
                val = ast.literal_eval(s)
                return normalize_to_parsed(val)
            except Exception:
                pass
        return visited_tracker.parse_sexpr(s)
    return str(tree_input)

def get_truth_table(tree_input, vars_list):
    parsed = normalize_to_parsed(tree_input)
    table = []
    n_vars = len(vars_list)
    for i in range(1 << n_vars):
        env = {vars_list[bit]: bool((i >> bit) & 1) for bit in range(n_vars)}
        table.append(eval_tree(parsed, env))
    return tuple(table)

def _gen_subtree(vars_list, depth):
    if depth <= 0 or random.random() < 0.35:
        if random.random() < 0.15:
            return random.choice(["TRUE", "FALSE"])
        return random.choice(vars_list)
    op = random.choice(["AND", "OR", "NOT"])
    if op == "NOT":
        child = _gen_subtree(vars_list, depth - 1)
        return f"(NOT {child})"
    else:
        k = random.randint(2, 3)
        children = [_gen_subtree(vars_list, depth - 1) for _ in range(k)]
        return f"({op} {' '.join(children)})"

def generate_random_tree(vars_list, depth=3):
    op = random.choice(["AND", "OR"])
    k = random.randint(2, 3)
    children = [_gen_subtree(vars_list, depth - 1) for _ in range(k)]
    return f"({op} {' '.join(children)})"

def permute_siblings(parsed):
    if isinstance(parsed, str):
        return parsed
    op = parsed[0]
    children = [permute_siblings(c) for c in parsed[1:]]
    if op in ("AND", "OR") and len(children) > 1:
        # Reverse children
        children.reverse()
    return [op] + children

def format_parsed(parsed):
    if isinstance(parsed, str):
        return parsed
    return f"({parsed[0]} {' '.join(format_parsed(c) for c in parsed[1:])})"

def get_raw_tree(idx):
    try:
        s = int(str(idx))
    except Exception:
        s = 1
    random.seed(s + 12345)
    return generate_random_tree(VARS, depth=3)

def get_perm_tree(idx):
    try:
        s = int(str(idx))
    except Exception:
        s = 1
    random.seed(s + 12345)
    t = generate_random_tree(VARS, depth=3)
    parsed = visited_tracker.parse_sexpr(t)
    perm_parsed = permute_siblings(parsed)
    return format_parsed(perm_parsed)

def record_validation(raw_str, red1_str, red2_str, perm_red_str):
    global _tests_run, _semantic_failures, _idempotence_failures, _permutation_failures
    _tests_run += 1

    # 1. Semantic Preservation
    tt_raw = get_truth_table(raw_str, VARS)
    tt_red1 = get_truth_table(red1_str, VARS)
    if tt_raw != tt_red1:
        _semantic_failures.append({
            "raw": raw_str,
            "reduced": red1_str
        })

    # 2. Idempotence: cleanTree(cleanTree(x)) == cleanTree(x)
    p_red1 = normalize_to_parsed(red1_str)
    p_red2 = normalize_to_parsed(red2_str)
    if p_red1 != p_red2:
        _idempotence_failures.append({
            "first_reduction": red1_str,
            "second_reduction": red2_str
        })

    # 3. Sibling Permutation: cleanTree(permuted) == cleanTree(original)
    p_perm_red = normalize_to_parsed(perm_red_str)
    if p_red1 != p_perm_red:
        _permutation_failures.append({
            "original_reduced": red1_str,
            "permuted_reduced": perm_red_str
        })
    return True

def summarize_results():
    print("\n" + "="*70)
    print("REDUCTION PROPERTIES VALIDATION SUMMARY")
    print("="*70)
    print(f"Total random trees tested:          {_tests_run}")
    print(f"Semantic preservation violations:   {len(_semantic_failures)}")
    print(f"Idempotence violations:             {len(_idempotence_failures)}")
    print(f"Sibling permutation differences:    {len(_permutation_failures)}")
    
    if _semantic_failures:
        print("\n[CRITICAL WARNING] Semantic preservation failed on:")
        for f in _semantic_failures[:3]:
            print(f"  Raw:     {f['raw']}")
            print(f"  Reduced: {f['reduced']}")
    else:
        print("\n[PASSED] Semantic preservation 100% verified (truth tables perfectly preserved).")

    if _idempotence_failures:
        print("\n[WARNING] Idempotence failed on:")
        for f in _idempotence_failures[:3]:
            print(f"  1st pass: {f['first_reduction']}")
            print(f"  2nd pass: {f['second_reduction']}")
    else:
        print("[PASSED] Idempotence 100% verified (cleanTree reaches a fixed point).")

    if _permutation_failures:
        print(f"\n[FINDING] Sibling permutation invariance failed on {len(_permutation_failures)}/{_tests_run} trees.")
        print("  -> Confirms that cleanTree alone does NOT canonicalize child ordering.")
        print("  -> Proves that visited_tracker.canonicalize_tree is strictly necessary.")
        print("  Sample differences:")
        for f in _permutation_failures[:3]:
            print(f"    Orig reduced: {f['original_reduced']}")
            print(f"    Perm reduced: {f['permuted_reduced']}")
    else:
        print("[PASSED] Sibling permutation invariance verified.")
    print("="*70 + "\n")
    return len(_semantic_failures) == 0
