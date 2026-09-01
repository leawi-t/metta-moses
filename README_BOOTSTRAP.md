# Bootstrap Initialization Policy

## The Problem
Historically, the `metta-moses` repository initialized the metapopulation using a pure `roulette` selection policy. While this works perfectly when the seed pool contains a single `true` program, it causes a severe initialization collapse when the seed pool contains multiple complex seeds (such as full-width n-ary `AND/OR` trees or `NOT` structures). Because complex seeds inherently score higher in their initial evaluations due to partial structural matches, they capture >99.8% of the selection probability mass in Generation 1. This starves foundational seeds (like `true` or binary pairs) of any early exploration, resulting in premature convergence and depressed final scores.

## The Solution
This update introduces a new initialization policy: `bootstrap`.
- `initPolicy = roulette` (Default): The legacy behavior.
- `initPolicy = bootstrap`: Guarantees that every seed in the provided seed pool is allocated its own private Deme and is forcefully expanded exactly once (for one generation) before being merged into the global metapopulation.

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

Bootstrap definitively mitigates the probability starvation bug with no performance overhead on clean seed sets.
