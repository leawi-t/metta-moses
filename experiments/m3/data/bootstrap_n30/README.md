# Recorded `parity3` N-ary Bootstrap Comparison

This directory contains the raw results for the recorded confirmation batch:

| Condition | Seed range | Mean final score | Exact solves | Process errors |
| --- | --- | ---: | ---: | ---: |
| `N-R` (`roulette`) | 0--29 | -3.2857 | 0/30 | 0/30 |
| `N-B` (`bootstrap`) | 0--29 | -3.0238 | 0/30 | 0/30 |

Each `seed_<n>.json` file records the seed, condition, final best score,
exact-solve flag, wall time, and process-error flag. The matching `.log` file
contains the captured engine output. `moses.metta` is the generated program
used for that condition.

Recorded parameters:

```text
git revision: 298be4cd56760b72c9d875e635b0c635cfc5e2ba
problem: parity3
maxGen: 50
nDeme: 1
optAlgo: hc
fsAlgo: None
complexityRatio: 3.5
nEval: 10000
capCoef: 50
discProbe: false
```

The generated programs use the historical injection runner documented in
`../../scripts/run_decisive_bootstrap.py`; see the parent README for the
important distinction between this recorded historical run and the final
native bootstrap implementation.
