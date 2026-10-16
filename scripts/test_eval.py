import sys
sys.path.insert(0, "scripts")
import candidate_collector

raw_expr = "(OR (AND (OR)) X1 (AND))"
tt_raw = candidate_collector.get_truth_table(raw_expr, ["X1", "X2", "X3", "X4"])
parsed = candidate_collector.parse_sexpr(raw_expr)
print("Parsed raw:", parsed)
print("TT for raw:", sum(tt_raw), "ones out of", len(tt_raw))

tt_clean = candidate_collector.get_truth_table("X1", ["X1", "X2", "X3", "X4"])
print("TT for X1:", sum(tt_clean), "ones out of", len(tt_clean))
