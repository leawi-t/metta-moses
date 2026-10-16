# Representation Building, Revisit Guard & Reduction Soundness Experiments

This README documents the architectural enhancements, bug fixes, and empirical investigations implemented on the `experiement/representation-building` branch of MOSES.

---

## Table of Contents
1. [Exemplar Revisit Guard (`--maxRevisits`)](#1-exemplar-revisit-guard---maxrevisits)
2. [Symmetric Polarity Representation (`--permPolarityMode`, `--logicalPermRatio`)](#2-symmetric-polarity-representation)
3. [Boolean Reducer Soundness Fix](#3-boolean-reducer-soundness-fix)
4. [Benchmark Suite & Complexity Penalty Analysis](#4-benchmark-suite--complexity-penalty-analysis)
5. [CLI Flags & Hyperparameters](#5-cli-flags--hyperparameters)
6. [Verification & Testing](#6-verification--testing)

---

## 1. Exemplar Revisit Guard (`--maxRevisits`)

### The Problem: Circular Deme Re-expansions
In classic MOSES, exemplar selection from the metapopulation is driven by penalized fitness via roulette selection. When the search enters a fitness plateau (especially on deceptive boolean functions like parity), a single top-ranking exemplar tree is repeatedly chosen across multiple generations.

On standard runs, **over 96% of deme expansions were redundant evaluations of the same exemplar tree**, re-sampling the same local knob neighborhood repeatedly without discovering new improving mutations.

### The Mechanism: Canonical Tree Tracking
To prevent circular re-expansion, we implemented `scripts/visited_tracker.py` and hooked it directly into `metapopulation/exemplar-selection.metta`:

1. **Semantic Canonical Normal Form:**
   Before tracking, program trees are normalized to collapse purely syntactic distinctions:
   - **Associative Flattening:** `(AND (AND A B) C)` $\rightarrow$ `(AND A B C)`.
   - **Commutative Sorting:** `(AND C A B)` $\rightarrow$ `(AND A B C)`.
   - **Duplicate Elimination:** `(OR A B A)` $\rightarrow$ `(OR A B)`.
   - **Double-Negation Elimination:** `(NOT (NOT X))` $\rightarrow$ `X`.
   - **Symbol Preservation:** Distinguishes feature names (`T`, `1`, `0`) from boolean constants (`TRUE`, `FALSE`) to avoid semantic collisions.

2. **Eligibility Filtering:**
   During `selectExemplar`, candidates whose canonical form has already been expanded $\ge \text{maxRevisits}$ times (default: `1`) are excluded from the roulette selection pool.

3. **Fallback Safety:**
   If all exemplars in the metapopulation reach `maxRevisits`, the search logs `[VISITED] All exemplars at revisit limit! Falling back to metapop.` and samples from the full metapopulation to ensure search continuity.

### Empirical Results of the Revisit Guard
- **Zero Duplicate Expansions:** Redundant deme expansions dropped from **96.7% $\rightarrow$ 0.0%**. Every single deme expansion explores a structurally distinct region of the program space.
- **Metapopulation Exploration:** The number of unique canonical exemplars explored per seed expanded from $\sim 1.5$ to $15–20$.
- **Interaction with Penalty Trade-offs:** On `parity4`, visited tracking prevents cycling, but breaking the raw $-3.0$ ceiling requires pairing visited tracking with an appropriate complexity ratio ($r^* \approx 100$).

---

## 2. Symmetric Polarity Representation

### The Polarity Asymmetry Finding
Classic MOSES generates pairwise permutation candidate subtrees in `getArgsClassic`. Inspection revealed an unintended structural sign bias:
For any ordered variable index pair $(a, b)$ with $a < b$:
- When $b > a$, emits $(X_a \land X_b)$.
- When $a < b$, emits $(\neg X_a \land X_b)$.
- **The clauses $(X_a \land \neg X_b)$ and $(\neg X_a \land \neg X_b)$ were NEVER generated (0% reachability).**

Consequences:
1. Pairwise XOR building blocks require both polarities: $(X_a \land \neg X_b) \lor (\neg X_a \land X_b)$. Because $(X_a \land \neg X_b)$ was missing, half of every XOR building block was unreachable.
2. The highest-index variable (e.g. $X_4$ on 4-variable problems) never appeared negated in any pairwise clause.

### The 4-Sign Symmetric Generator
In `representation/sample-logical-perms.metta`, we implemented clean dual-mode sampling:
1. `genUnorderedPairs`: Enumerate all distinct unordered pairs $(a, b)$ with $a < b$.
2. `emitFourSignVariants`: For each pair, emit all four complete sign combinations:
   - $(X_a \land X_b)$
   - $(X_a \land \neg X_b)$
   - $(\neg X_a \land X_b)$
   - $(\neg X_a \land \neg X_b)$
3. Deduplicate via `unique-atom`.
4. `sampleFromList`: Uniformly sample $k = \min(|L|, \text{floor}(\text{arity} \times \text{logicalPermRatio}))$ clauses without replacement.

### Empirical Findings
Controlled benchmarks on `parity4` and `parity5` demonstrated that isolated pairwise XOR clauses correlate with the truth table on exactly 50% of rows (zero fitness gradient). Thus, representation richness alone does not break the parity plateau at small budgets without metapopulation diversification or penalty calibration.

---

## 3. Boolean Reducer Soundness Fix

### The Inconsistent Handle Leak
During truth-table differential testing across random boolean trees, a latent reducer bug was discovered:
When `deleteInconsistentHandle` eliminated a contradictory POA under an `OR` parent, if the parent was left as an empty structure or evaluated to `FALSE` (e.g. `(OR FALSE (AND X2 (NOT X2)))`), the intermediate result became `(OR FALSE)`.

Because prior code only checked `(== $withoutPOA (OR))`, the expression `(OR FALSE)` was not recognized as a constant. It bypassed reduction and leaked into `(OR)` / `(AND)`, which evaluated to `TRUE` instead of `FALSE`.

### Resolution & Test Suite
1. **Patched Modules:**
   - `reduct/boolean-reduct/delete-inconsistent-handle.metta`: Added `(or (== $withoutPOA (OR)) (== (applyConstantLaws $withoutPOA) FALSE))` to force canonical `FALSE` propagation.
   - `reduct/boolean-reduct/reduce-to-elegance.metta`: Added constant propagation in `applyReduce`.
2. **Regression Test Suite:**
   - Added `reduct/boolean-reduct/tests/test_reduct_fix.metta`:
     - `(reduce-to (OR FALSE (AND X2 (AND X2 X2 X3) (NOT X3))))` $\rightarrow$ `FALSE` ✅
     - `(reduce-to (OR (AND X2 (AND X2 X2 X3) (NOT X3)) FALSE))` $\rightarrow$ `FALSE` ✅
     - `(reduce-to (OR FALSE FALSE))` $\rightarrow$ `FALSE` ✅
3. **Empirical Incidence:**
   Probing live MOSES runs showed the trigger condition occurs in $\sim 0.14\%$ of handle evaluations. A paired 15-seed benchmark confirmed 100% numerical and candidate preservation.

---

## 4. Benchmark Suite & Complexity Penalty Analysis

### Native Problem Definitions Added
In `moses/demo-problems.metta`:
- `--problem=parity5`: 5-bit odd parity ($2^5 = 32$ rows).
- `--problem=majority7`: 7-bit majority ($2^7 = 128$ rows; true when 4 or more inputs are true).

### Dense Ratio Sweep & Minimum Effective Ratio ($r^*$)
Across 360 paired runs ($N=20$ paired seeds, ratios $14, 20, 50, 100, 300, 1000$):

| Problem | Ratio | Breakout Rate | Median Raw | Mean Literals | Notes |
|:---|:---:|:---:|:---:|:---:|:---|
| **`parity4`** | $14.0 - 50.0$ | $26.3\% - 35.0\%$ | $-3.0$ | $\sim 13.7$ | Blocked by steep complexity penalty |
| **`parity4`** | **$100.0$** | **$52.6\%$** | **$-2.0$** | **$15.9$** | **Minimum effective ratio $r^*$ (ceiling broken)** |
| **`parity4`** | $300.0 - 1000.0$ | $50.0\% - 52.6\%$ | $-2.0$ | $16.0$ | Diminishing returns |
| **`parity5`** | $14.0 - 20.0$ | $75.0\%$ | $-13.0$ | $7.5 - 7.8$ | Baseline chance level is $-16.0$ |
| **`parity5`** | **$50.0 - 100.0$** | **$90.0\%$** | **$-12.0$** | **$9.6 - 10.1$** | **$r^*$ for parity5; gains up to $+6.0$** |
| **`majority5`** | $14.0 - 300.0$ | $78.9\% - 95.0\%$ | $-1.0 - 0.0$ | $13.2 - 15.4$ | Solve rate up to $52.6\%$ |
| **`majority5`** | $1000.0$ | $93.8\%$ | $-1.0$ | $15.6$ | **Bloat timeout: 4 seeds exceeded 300s timeout** |
| **`majority7`** | $3.5 - 1000.0$ | $0.0\%$ | $-19.0$ | — | **True topological plateau (unaffected by ratio)** |

**Key Takeaways:**
1. `parity4`'s stall at $-3.0$ was largely an **objective trade-off artifact**: a 15-literal $-2.0$ candidate was rejected under default ratio $3.5$ because the complexity penalty $(-15/3.5)$ exceeded the raw fitness gain. Setting $r^* = 100$ resolves this without bloat.
2. `majority7` is a **true topological search plateau** that cannot be solved by penalty relaxation alone.
3. Unbounded penalty relaxation ($r \ge 1000$) invites **computational bloat**, leading to runtime timeouts during tree reduction.

---

## 5. CLI Flags & Hyperparameters

| Flag | Default | Description |
|:---|:---:|:---|
| `--maxRevisits=<int>` | `1` | Maximum times any canonical exemplar tree can be expanded before being excluded from roulette selection. |
| `--permPolarityMode=<str>` | `classic` | Permutation generator mode: `classic` (asymmetric) or `symmetric` (full 4-sign variants). |
| `--logicalPermRatio=<float>` | `1.0` | Clause expansion sampling budget multiplier. |
| `--complexityRatio=<float>` | `3.5` | Complexity penalty divisor. Use `100.0` for parity4 breakout. |
| `--problem=<str>` | — | Benchmark problem: `parity3`, `parity4`, `parity5`, `majority3`, `majority5`, `majority7`, `mux3`, `mux6`, `disjunction3`. |

---

## 6. Verification & Testing

### Running Unit Tests

```sh
# 1. Python canonicalization & visited tracking unit tests
python3 scripts/test_visited_unit.py

# 2. Python telemetry & logger unit tests
python3 scripts/test_logger_helper_unit.py

# 3. MeTTa boolean reduct soundness fix test
./PeTTa/run.sh reduct/boolean-reduct/tests/test_reduct_fix.metta -s

# 4. MeTTa symmetric representation test
./PeTTa/run.sh representation/tests/sample-logical-perms-symmetric-test.metta -s

# 5. Full test suite
python3 scripts/run-tests.py
```
