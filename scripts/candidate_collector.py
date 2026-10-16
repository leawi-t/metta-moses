import sys
import os

VARS_BY_PROBLEM = {
    "parity3": ["X1", "X2", "X3"],
    "parity4": ["X1", "X2", "X3", "X4"],
    "parity5": ["X1", "X2", "X3", "X4", "X5"],
    "majority3": ["A", "B", "C"],
    "majority5": ["X1", "X2", "X3", "X4", "X5"],
    "disjunction3": ["X1", "X2", "X3"],
    "mux3": ["Addr", "D0", "D1"],
}

_current_problem = "parity4"
_total_candidates = 0
_semantic_corruptions = []
_active = False

def set_problem(problem_name):
    global _current_problem, _active
    _current_problem = str(problem_name)
    _active = True
    return True

def reset():
    global _total_candidates, _semantic_corruptions, _active
    _total_candidates = 0
    _semantic_corruptions = []
    _active = False
    return True

def parse_sexpr(s):
    s = str(s).strip()
    if not s.startswith("(") or not s.endswith(")"):
        return s
    tokens = []
    cur = []
    depth = 0
    in_token = False
    for char in s[1:-1]:
        if char == "(":
            depth += 1
            cur.append(char)
        elif char == ")":
            depth -= 1
            cur.append(char)
            if depth == 0:
                tokens.append(parse_sexpr("".join(cur)))
                cur = []
        elif char in (" ", "\t", "\n", "\r"):
            if depth == 0:
                if cur:
                    tokens.append("".join(cur))
                    cur = []
            else:
                cur.append(char)
        else:
            cur.append(char)
    if cur:
        tokens.append("".join(cur))
    return tokens

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
    # Atoms or constants
    p_str = str(parsed).upper()
    if p_str in ('TRUE', '1'):
        return True
    if p_str in ('FALSE', '0'):
        return False
    return env.get(str(parsed), False)

def get_truth_table(tree_expr, vars_list):
    parsed = parse_sexpr(tree_expr)
    n_vars = len(vars_list)
    table = []
    for i in range(1 << n_vars):
        env = {vars_list[bit]: bool((i >> bit) & 1) for bit in range(n_vars)}
        table.append(eval_tree(parsed, env))
    return tuple(table)

def record_candidate(raw_str, cleaned_str):
    global _total_candidates, _semantic_corruptions, _active, _current_problem
    if not _active:
        return True
    
    _total_candidates += 1
    raw_s = str(raw_str)
    cleaned_s = str(cleaned_str)
    
    # Fast path if strings are identical
    if raw_s == cleaned_s:
        return True
        
    vars_list = VARS_BY_PROBLEM.get(_current_problem, ["X1", "X2", "X3", "X4", "X5"])
    try:
        tt_raw = get_truth_table(raw_s, vars_list)
        tt_clean = get_truth_table(cleaned_s, vars_list)
        if tt_raw != tt_clean:
            _semantic_corruptions.append({
                "candidate_idx": _total_candidates,
                "raw": raw_s,
                "cleaned": cleaned_s,
                "raw_tt_ones": sum(tt_raw),
                "clean_tt_ones": sum(tt_clean),
                "total_rows": len(tt_raw)
            })
    except Exception as e:
        # Ignore parse or evaluation errors for exotic non-boolean terms
        pass
    return True

def get_summary():
    global _total_candidates, _semantic_corruptions
    return {
        "total_candidates": _total_candidates,
        "corruptions_count": len(_semantic_corruptions),
        "corruption_rate": len(_semantic_corruptions) / max(1, _total_candidates),
        "corruptions": _semantic_corruptions[:10]
    }
