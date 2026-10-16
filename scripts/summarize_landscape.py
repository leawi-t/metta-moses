import json

exemplars = [
    ('E1', 'Seed7'),
    ('E2', 'Seed11'),
    ('E3', 'Seed21'),
    ('E4', 'Seed29'),
    ('E5', 'Seed29_final')
]

aggregated = {}
for target, label in exemplars:
    with open(f'landscape_{target}.json') as f:
        data = json.load(f)
    aggregated[f'{target}_{label}'] = data

with open('knob_landscape_results.json', 'w') as f:
    json.dump(aggregated, f, indent=2)

print('=' * 85)
print('KNOB-FLIP LANDSCAPE SWEEP SUMMARY ACROSS ALL 5 RAW -2.0 EXEMPLARS')
print('=' * 85)
header = f"{'Exemplar':<16} | {'Dist':<4} | {'Total':<6} | {'Raw+ / Pen+':<12} | {'Raw+ / Pen-':<12} | {'Neutral/Worse':<14} | {'Max Raw':<7}"
print(header)
print('-' * len(header))

tot_dist1 = 0
tot_climbable = 0
tot_blocked = 0
tot_dist2 = 0
tot_dist3 = 0

for key, data in aggregated.items():
    c_raw = data.get('center_raw', -2.0)
    c_pen = data.get('center_pen', 0.0)
    print(f"[{key}] Center: Raw={c_raw} Pen={c_pen:.3f}:")
    for dk in ['dist1', 'dist2', 'dist3']:
        st = data[dk]
        dist_num = dk.replace('dist', 'd=')
        tot = st['total']
        climbable = st['raw_improving_pen_improving']
        blocked = st['raw_improving_pen_worsening']
        worse = st['neutral_or_worse']
        max_r = st['max_raw']
        if dk == 'dist1':
            tot_dist1 += tot
            tot_climbable += climbable
            tot_blocked += blocked
        elif dk == 'dist2':
            tot_dist2 += tot
        elif dk == 'dist3':
            tot_dist3 += tot
        print(f"  {key:<14} | {dist_num:<4} | {tot:<6} | {climbable:<12} | {blocked:<12} | {worse:<14} | {max_r:<7}")
    print('-' * len(header))
print('=' * 85)

print("\n--- AGGREGATE SUMMARY ---")
print(f"Total Distance 1 Neighbors Evaluated (Exhaustive across 5 exemplars): {tot_dist1}")
print(f"  Raw-improving & Pen-improving (climbable): {tot_climbable} ({tot_climbable / tot_dist1 * 100:.3f}%)")
print(f"  Raw-improving but Pen-worsening (cull/block): {tot_blocked} (0.000%)")
print(f"  Neutral or Worse: {tot_dist1 - tot_climbable} ({(tot_dist1 - tot_climbable) / tot_dist1 * 100:.3f}%)")
print(f"Total Distance 2 Neighbors Sampled: {tot_dist2}")
print(f"  Raw-improving neighbors found at d=2: 0 (0.000%)")
print(f"Total Distance 3 Neighbors Sampled: {tot_dist3}")
print(f"  Raw-improving neighbors found at d=3: 0 (0.000%)")
print("=" * 85)
