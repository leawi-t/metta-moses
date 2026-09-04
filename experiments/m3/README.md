# M3: Metapopulation Initialization Experiments

This directory preserves the code, data, and documentation for the M3
metapopulation-initialization investigation in MeTTa-MOSES.

## Scope

The controlled result in this directory tests one specific question on
`parity3`:

> Can bootstrap initialization mitigate roulette-selection dominance caused by
> a seed pool that contains full-width n-ary Boolean programs?

The `pairs_nary` pool contains `true`, four binary `AND`/`OR` pair seeds, and
full-width `AND(X1, X2, X3)` and `OR(X1, X2, X3)` seeds. `roulette` selects
the first exemplar using the normal score-weighted policy. `bootstrap`
expands each initial seed once, merges the resulting demes, and then uses the
normal search loop with the remaining top-level expansion budget.

## Finding

For the recorded 30-seed `parity3` comparison (`maxGen=50`, `nDeme=1`):

| Condition | Mean final score |
| --- | ---: |
| `pairs_nary` + `roulette` | -3.2857 |
| `pairs_nary` + `bootstrap` | -3.0238 |

The paired mean difference (`bootstrap - roulette`) was `+0.2619`, with a
reported bootstrap 95% confidence interval of `[+0.1571, +0.3667]` and a
Wilcoxon signed-rank p-value of `0.00025`. Scores closer to zero are better.

This supports the narrow conclusion that bootstrap **mitigated** the observed
n-ary initialization-selection collapse in this configuration. It does not
establish bootstrap as a general MOSES improvement, prove that it has no cost
on clean seed pools, or demonstrate improved exact-solve rate.

## Code on this branch

The implementation adds:

- `initPolicy=roulette|bootstrap`, with `roulette` as the default;
- `seedPool=legacy|pairs|pairs_nary`, with `legacy` as the default;
- `bootstrapDemes`, which expands each initial exemplar once before merge;
- unique expansion-index increments during the normal `runMoses` loop; and
- diagnostic logging used while investigating selection behavior.

See [README_BOOTSTRAP.md](../../README_BOOTSTRAP.md) for the public
configuration interface. The smoke test is
`moses/tests/bootstrap-smoke-test.metta`.

## Data provenance and reproduction status

`data/bootstrap_n30/` contains the raw per-seed logs and JSON summaries from
the recorded decisive comparison. The data was produced before the native
`seedPool` implementation was finalized, using the historical code-injection
runner in `scripts/run_decisive_bootstrap.py`.

That runner is retained to document the historical experiment. It is **not** a
reproduction command for the final native implementation in this branch: it
patches a historical `moses-run` and seed-scoring path. A future native rerun
using `seedPool=pairs_nary` and `initPolicy=roulette|bootstrap` is required
before claiming that the recorded numerical result reproduces the final code
unchanged.

The historical runner uses an isolated temporary Git worktree and refuses to
overwrite a non-empty output directory. Its `--output-dir` option should point
to a new empty local-results directory.

## Historical exploratory experiments

The investigation also included earlier experiments that predate the native
bootstrap implementation. These are documented in
[HISTORICAL.md](HISTORICAL.md). They provide research context, but are not
directly comparable to the controlled result above and are not advertised as
runnable from this branch without their exact historical revision and
configuration.
