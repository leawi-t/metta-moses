# Historical M3 Exploratory Experiments

These experiments motivated the controlled bootstrap comparison, but were run
before the native bootstrap implementation and the current experiment branch
were established. Treat them as exploratory observations rather than results
that can be reproduced from the current branch without recovering their exact
revision, harness, and configuration.

## Experiment 1: Uninformed / tautology seeds

Task-agnostic seed programs were added to the initial metapopulation to test
whether diversity alone improved search.

seed pool used:

```text
{true,
OR(v, NOT(v)),
AND(v, NOT(v))}
```

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

Did in case just Two variable motifs was not enough data.
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

## Experiment Data

### Experiment 1

| Problem | Baseline MBF | Exp1 MBF | ΔMBF | Baseline AvgGen | Exp1 AvgGen | Δ Gen | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| parity3 | -0.70 | -0.40 | +0.30 | 31.0 | 19.5 | 11.5 | Strong improvement |
| majority5 | -2.00 | -1.70 | +0.30 | 50.0 | 50.0 | 0 | Better score, same speed |
| parity4 | -3.90 | -4.40 | -0.50 | 50.0 | 50.0 | 0 | Slight regression |
| disjunction3 | 0.00 | 0.00 | 0 | 2.0 | 2.0 | 0 | No change |
| majority3 | 0.00 | 0.00 | 0 | 2.7 | 2.6 | -0.1 | No change |
| mux3 | 0.00 | 0.00 | 0 | 2.0 | 2.1 | +0.1 | No change |
| mux6 | 0.00 | 0.00 | 0 | 7.2 | 6.8 | -0.4 | Slightly faster |

### Experiment 2

| Problem | MBF | Avg Gen |
| :--- | :--- | :---: |
| parity3 | -0.53 | 24.0 |
| parity4 | -3.9 (matches baseline) | — |
| majority5 | -2.0 (matches baseline) | — |

### Experiment 2.1

| Problem | MBF | Avg Gen | Success Rate |
| :--- | :--- | :---: | :---: |
| parity3 | -1.10 (n=30 version) / -1.00 (n=10 version) | 37.4 | 33% |
| parity4 | -4.4 | 50 | — |
| majority5 | -2.0 | 50 | — |
