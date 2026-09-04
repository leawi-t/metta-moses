# Historical M3 Exploratory Experiments

These experiments motivated the controlled bootstrap comparison, but were run
before the native bootstrap implementation and the current experiment branch
were established. Treat them as exploratory observations rather than results
that can be reproduced from the current branch without recovering their exact
revision, harness, and configuration.

## Experiment 1: Uninformed / tautology seeds

Task-agnostic seed programs were added to the initial metapopulation to test
whether diversity alone improved search.

- `parity3` and `mux6` improved modestly.
- `parity4` became worse.
- `majority5` improved slightly.

The result suggested that additional initial diversity can affect outcomes,
but that it is neither sufficient nor consistently beneficial across tasks.

## Experiment 2: Two-variable Boolean motifs

The seed pool used small structured motifs such as:

```text
true
AND(v1, v2)
OR(v1, v2)
AND(v1, NOT(v2))
OR(v1, NOT(v2))
```

This experiment motivated examination of whether useful Boolean building
blocks were receiving meaningful early search exposure.

## Experiment 2.1: Arity-generalized seeds

The seed construction was generalized using the input-variable list:

- `buildAllVarsTree` created full-width n-ary `AND`/`OR` programs;
- `buildPairSeeds` created adjacent two-variable `AND`/`OR` programs; and
- `parity3` therefore used seven seeds in total.

The resulting parity3 behavior led to the n-ary isolation diagnostic. That
diagnostic showed that the full-width seeds received disproportionately high
initial roulette weight, which motivated bootstrap initialization.

## Reproduction note

Do not add commands here unless the original source revision, parameters,
runner, and result artifacts are recovered. The paper may cite these
experiments as the exploratory sequence that motivated the controlled
bootstrap study.
