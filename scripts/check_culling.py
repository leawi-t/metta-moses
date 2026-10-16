import json

with open('long_horizon_visited_stats.json') as f:
    data = json.load(f)

p4_visited = [r for r in data if r.get('problem') == 'parity4' and r.get('arm') == 'B_visited']
print(f"Total parity4 B_visited runs: {len(p4_visited)}")

culled_list = [r.get('distinct_culled', 0) for r in p4_visited]
print("Distinct culled per seed:", culled_list)
print("Mean distinct culled:", sum(culled_list) / len(culled_list))

best_raws = [r.get('best_raw') for r in p4_visited]
print("Best raws:", best_raws)

# Check per-gen progression of culled candidates
print("\nExamining seeds where raw was -3 or -2:")
for r in p4_visited[:5]:
    seed = r.get('seed')
    prog = r.get('progression', [])
    print(f"Seed {seed}: Final BestRaw={r.get('best_raw')}, DistinctCulled={r.get('distinct_culled')}")
    for p in prog[-3:]:
        print(f"   Gen {p.get('gen')}: BestRaw={p.get('best_raw')}, Lits={p.get('literals')}, BestPen={p.get('best_pen')}, CulledThisGen={p.get('culled_this_gen')}, DistinctCulledTotal={p.get('distinct_culled_total')}")
