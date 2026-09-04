# Bootstrap Initialization Policy

## The Problem
Historically, the `metta-moses` repository initialized the metapopulation using a pure `roulette` selection policy. In the tested `parity3` pool containing full-width n-ary `AND`/`OR` programs, small initial-score differences assigned almost all first-selection probability mass to the n-ary seeds. This starved `true` and binary-pair seeds of early exploration and led to a poor search trajectory. This observation is specific to the tested seed pool and scorer; it does not imply that every complex or `NOT`-containing seed behaves this way.

## The Solution
This update introduces a new initialization policy: `bootstrap`.
- `initPolicy = roulette` (Default): The legacy behavior.
- `initPolicy = bootstrap`: Guarantees that every seed in the provided seed pool is allocated its own private Deme and is forcefully expanded exactly once (for one generation) before being merged into the global metapopulation.

`bootstrap` requires `maxGen` to be at least the number of seeds in the
selected pool. When the budget is smaller, the implementation logs the issue
and falls back to `roulette` rather than silently exceeding the budget.

## Usage
You can configure the initial seed pool and the initialization policy via `&params`:

```metta
!(set-param seedPool legacy)       ;; Default: only `true`
!(set-param seedPool pairs)        ;; `true` + 4 binary pairs
!(set-param seedPool pairs_nary)   ;; `true` + pairs + full-width n-ary

!(set-param initPolicy roulette)   ;; Default: legacy probability-based selection
!(set-param initPolicy bootstrap)  ;; Guarantees fair evaluation of all seeds
```

## Statistical Proof
In a 30-seed rigorous benchmark on `parity3`, using the `pairs_nary` pool:
- `roulette` mean score: -3.2857
- `bootstrap` mean score: -3.0238
- Mean paired improvement: +0.2619 (Wilcoxon p-value = 0.00025, p < 0.001).

For the tested `parity3` n-ary seed pool, bootstrap mitigated the observed
selection-collapse mechanism. It has not been established as a universal
improvement or as cost-free on clean seed pools.
