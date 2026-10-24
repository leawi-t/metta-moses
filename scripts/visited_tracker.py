import collections

_visit_counts = collections.defaultdict(int)
_fallback_count = 0

def parse_sexpr(s):
    if not isinstance(s, str):
        return s
    s = s.strip()
    if not (s.startswith('(') and s.endswith(')')):
        return s
    tokens = s.replace('(', ' ( ').replace(')', ' ) ').split()
    def _parse(toks):
        if not toks:
            return None
        t = toks.pop(0)
        if t == '(':
            sub = []
            while toks and toks[0] != ')':
                sub.append(_parse(toks))
            if toks and toks[0] == ')':
                toks.pop(0)
            return sub
        elif t == ')':
            return None
        return t
    return _parse(tokens)

def canonicalize_tree(expr):
    """
    Recursively canonicalizes a boolean tree expression into a deterministic form.
    AND and OR children are flattened, recursively canonicalized, deduplicated, 
    and lexicographically sorted.
    """
    # Check bool first before int since bool is subclass of int in Python
    if isinstance(expr, bool):
        return 'TRUE' if expr else 'FALSE'

    if isinstance(expr, str):
        s = expr.strip()
        if s.startswith('(') and s.endswith(')'):
            parsed = parse_sexpr(s)
            if isinstance(parsed, (list, tuple)):
                return canonicalize_tree(parsed)
        if s in ('True', 'TRUE', 'true'):
            return 'TRUE'
        if s in ('False', 'FALSE', 'false'):
            return 'FALSE'
        return s

    if isinstance(expr, (int, float)):
        return str(expr)
        
    # Check for Janus compound term if present
    if hasattr(expr, 'name') and hasattr(expr, 'args'):
        expr = (expr.name, *expr.args)

    if not isinstance(expr, (list, tuple)):
        s = str(expr).strip()
        if s.startswith('(') and s.endswith(')'):
            parsed = parse_sexpr(s)
            if isinstance(parsed, (list, tuple)):
                return canonicalize_tree(parsed)
        return s
        
    if len(expr) == 0:
        return '()'
        
    op = str(expr[0]).strip().upper()
    
    if op in ('AND', 'OR'):
        canon_children = []
        for child in expr[1:]:
            canon_child = canonicalize_tree(child)
            # Flatten associative operators
            if isinstance(canon_child, tuple) and canon_child[0] == op:
                canon_children.extend(canon_child[1:])
            else:
                canon_children.append(canon_child)
                
        # Deduplicate identical subtrees under same junctor
        unique_children = []
        seen = set()
        for c in canon_children:
            s_c = tree_to_str(c) if isinstance(c, tuple) else str(c)
            if s_c not in seen:
                seen.add(s_c)
                unique_children.append(c)
                
        # Lexicographically sort children
        unique_children.sort(key=lambda x: tree_to_str(x) if isinstance(x, tuple) else str(x))
        
        if len(unique_children) == 1:
            return unique_children[0]
        return (op, *unique_children)
        
    elif op == 'NOT':
        if len(expr) > 1:
            child = canonicalize_tree(expr[1])
            if isinstance(child, tuple) and child[0] == 'NOT' and len(child) > 1:
                return child[1]
            return ('NOT', child)
        return ('NOT',)
    else:
        return (str(expr[0]), *(canonicalize_tree(c) for c in expr[1:]))

def tree_to_str(node):
    if isinstance(node, tuple):
        return "(" + " ".join(tree_to_str(c) for c in node) + ")"
    return str(node)

def get_canonical_key(tree_expr):
    return tree_to_str(canonicalize_tree(tree_expr))

def reset():
    global _visit_counts, _fallback_count
    _visit_counts.clear()
    _fallback_count = 0
    return True

def get_visit_count(tree_expr):
    key = get_canonical_key(tree_expr)
    return _visit_counts[key]

def is_eligible(tree_expr, max_revisits=1):
    key = get_canonical_key(tree_expr)
    count = _visit_counts[key]
    return 1 if count < max_revisits else 0

def record_visit(tree_expr):
    key = get_canonical_key(tree_expr)
    _visit_counts[key] += 1
    return _visit_counts[key]

def record_fallback():
    global _fallback_count
    _fallback_count += 1
    print(f"(Step2-Fallback Count: {_fallback_count})", flush=True)
    return _fallback_count

def get_fallback_count():
    return _fallback_count

def stats():
    return {
        "unique_keys": len(_visit_counts),
        "total_visits": sum(_visit_counts.values()),
        "fallback_count": _fallback_count,
        "counts": dict(_visit_counts)
    }
