import sys
import json
import random
from collections import defaultdict

_current_exemplar = None
_exemplar_results = {}

def start_exemplar(name, raw, cpxy, pen):
    global _current_exemplar, _exemplar_results
    name = str(name)
    _current_exemplar = name
    _exemplar_results[name] = {
        "name": name,
        "center_raw": float(raw),
        "center_cpxy": float(cpxy),
        "center_pen": float(pen),
        "dist1": {
            "total": 0,
            "raw_improving_pen_improving": 0,
            "raw_improving_pen_worsening": 0,
            "neutral_or_worse": 0,
            "max_raw": float(raw),
            "raw_distribution": defaultdict(int),
            "improving_samples": []
        },
        "dist2": {
            "total": 0,
            "raw_improving_pen_improving": 0,
            "raw_improving_pen_worsening": 0,
            "neutral_or_worse": 0,
            "max_raw": float(raw),
            "raw_distribution": defaultdict(int),
            "improving_samples": []
        },
        "dist3": {
            "total": 0,
            "raw_improving_pen_improving": 0,
            "raw_improving_pen_worsening": 0,
            "neutral_or_worse": 0,
            "max_raw": float(raw),
            "raw_distribution": defaultdict(int),
            "improving_samples": []
        }
    }
    return True

def record_neighbor(dist, raw, cpxy, pen):
    global _current_exemplar, _exemplar_results
    if not _current_exemplar:
        return True
    d = _exemplar_results[_current_exemplar]
    dist_key = f"dist{int(dist)}"
    if dist_key not in d:
        return True
    
    stat = d[dist_key]
    stat["total"] += 1
    
    r = float(raw)
    p = float(pen)
    c = float(cpxy)
    stat["raw_distribution"][r] = stat["raw_distribution"].get(r, 0) + 1

    
    if r > stat["max_raw"]:
        stat["max_raw"] = r
        
    c_raw = d["center_raw"]
    c_pen = d["center_pen"]
    
    if r > c_raw:
        if p > c_pen:
            stat["raw_improving_pen_improving"] += 1
            if len(stat["improving_samples"]) < 5:
                stat["improving_samples"].append({"raw": r, "cpxy": c, "pen": p, "type": "improving_both"})
        else:
            stat["raw_improving_pen_worsening"] += 1
            if len(stat["improving_samples"]) < 5:
                stat["improving_samples"].append({"raw": r, "cpxy": c, "pen": p, "type": "penalty_blocked"})
    else:
        stat["neutral_or_worse"] += 1
        
    return True

def generate_random_instances(center_inst, spec_lists, dist, n_samples):
    """Generates n_samples unique random instances at exact Hamming distance `dist`."""
    c_inst = list(center_inst)
    K = len(c_inst)
    dist = int(dist)
    n_samples = int(n_samples)
    
    # Valid non-default choices for each knob
    specs = []
    for sp in spec_lists:
        if isinstance(sp, (list, tuple)):
            specs.append(list(sp))
        else:
            specs.append([1, 2])
            
    seen = set()
    samples = []
    attempts = 0
    max_attempts = n_samples * 10
    
    # Identify knobs that have valid choices
    valid_knob_indices = [i for i in range(K) if len(specs[i]) > 0]
    if len(valid_knob_indices) < dist:
        return ()
        
    while len(samples) < n_samples and attempts < max_attempts:
        attempts += 1
        picked_knobs = random.sample(valid_knob_indices, dist)
        inst = list(c_inst)
        for idx in picked_knobs:
            inst[idx] = random.choice(specs[idx])
        t_inst = tuple(inst)
        if t_inst not in seen and t_inst != tuple(c_inst):
            seen.add(t_inst)
            samples.append(list(inst))
            
    return samples

def save_partial_results(target_name):
    global _exemplar_results
    t_name = str(target_name)
    if t_name not in _exemplar_results and target_name not in _exemplar_results:
        print(f"Warning: {target_name} not found in {_exemplar_results.keys()}")
        return False
    data = _exemplar_results.get(t_name, _exemplar_results.get(target_name))
    serialized = {
        "name": data["name"],
        "center_raw": data["center_raw"],
        "center_cpxy": data["center_cpxy"],
        "center_pen": data["center_pen"],
    }
    for dk in ["dist1", "dist2", "dist3"]:
        st = data[dk]
        serialized[dk] = {
            "total": st["total"],
            "raw_improving_pen_improving": st["raw_improving_pen_improving"],
            "raw_improving_pen_worsening": st["raw_improving_pen_worsening"],
            "neutral_or_worse": st["neutral_or_worse"],
            "max_raw": st["max_raw"],
            "raw_distribution": {str(k): v for k, v in st["raw_distribution"].items()},
            "improving_samples": list(st["improving_samples"])
        }
    filename = f"landscape_{t_name}.json"
    with open(filename, "w") as f:
        json.dump(serialized, f, indent=2)
    print(f"Saved partial results to {filename}")
    return True

def finalize_and_save(filename="knob_landscape_results.json"):
    global _exemplar_results
    serialized = {}
    for name, data in _exemplar_results.items():
        entry = {
            "name": data["name"],
            "center_raw": data["center_raw"],
            "center_cpxy": data["center_cpxy"],
            "center_pen": data["center_pen"],
        }
        for dk in ["dist1", "dist2", "dist3"]:
            st = data[dk]
            entry[dk] = {
                "total": st["total"],
                "raw_improving_pen_improving": st["raw_improving_pen_improving"],
                "raw_improving_pen_worsening": st["raw_improving_pen_worsening"],
                "neutral_or_worse": st["neutral_or_worse"],
                "max_raw": st["max_raw"],
                "raw_distribution": {str(k): v for k, v in st["raw_distribution"].items()},
                "improving_samples": list(st["improving_samples"])
            }
        serialized[name] = entry
        
    with open(filename, "w") as f:
        json.dump(serialized, f, indent=2)

        
    print("\n" + "=" * 75)
    print("KNOB-FLIP LANDSCAPE ANALYSIS RESULTS (Across Raw -2 Exemplars)")
    print("=" * 75)
    for name, data in _exemplar_results.items():
        print(f"\n--- Exemplar: {name} ---")
        print(f"Center: Raw={data['center_raw']} | Complexity={data['center_cpxy']} | Penalized={data['center_pen']:.3f}")
        for dk in ["dist1", "dist2", "dist3"]:
            st = data[dk]
            if st["total"] == 0:
                continue
            print(f"  [{dk.upper()} - Evaluated {st['total']} neighbors]:")
            print(f"    Raw-improving & Pen-improving (climbable):     {st['raw_improving_pen_improving']}")
            print(f"    Raw-improving but Pen-worsening (cull/block):  {st['raw_improving_pen_worsening']}")
            print(f"    Neutral or Worse:                             {st['neutral_or_worse']}")
            print(f"    Max Raw score reached:                        {st['max_raw']}")
            print(f"    Raw Score distribution:                       {dict(st['raw_distribution'])}")
            if st['improving_samples']:
                print(f"    Sample improving neighbors:                   {st['improving_samples']}")
    print("=" * 75)
    return True
