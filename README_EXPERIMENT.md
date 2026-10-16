# Representation Building, Revisit Guard & Reduction Soundness Experiments

This README documents the architectural enhancements, bug fixes, and empirical investigations implemented on the `experiement/representation-building` branch of MOSES.

---

## Table of Contents
1. [Exemplar Revisit Guard (`--maxRevisits`)](#1-exemplar-revisit-guard---maxrevisits)
2. [Symmetric Polarity Representation (`--permPolarityMode`, `--logicalPermRatio`)](#2-symmetric-polarity-representation)
3. [Boolean Reducer Soundness Fix](#3-boolean-reducer-soundness-fix)
4. [Benchmark Suite & Complexity Penalty Analysis](#4-benchmark-suite--complexity-penalty-analysis)
5. [Stall-Triggered Complexity Ratio Relaxation](#5-stall-triggered-complexity-ratio-relaxation)
6. [Experimental Benchmark Suite](#6-experimental-benchmark-suite)
7. [CLI Flags & Hyperparameters](#7-cli-flags--hyperparameters)
8. [Verification & Experiment Execution](#8-verification--experiment-execution)

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

## 5. Stall-Triggered Complexity Ratio Relaxation

### The Motivation: Adaptive Penalty Modulation
Dense sweep results confirmed that while lower complexity ratios ($r=14$) enforce compact representations, they erect an artificial penalty barrier that culled promising intermediate candidates (e.g., rejecting $-2.0$ candidates with 15 literals on `parity4`). Conversely, statically relaxing the ratio everywhere ($r \ge 1000$) invites bloat and runtime timeouts.

Rather than running statically relaxed, **Stall-Triggered Complexity Ratio Relaxation** maintains a parsimonious baseline penalty ($r_{\text{base}} = 14.0$) and dynamically relaxes the penalty ($r_{\text{relax}} = 100.0$) **only when the search hits an empirical fitness stall**.

### The Mechanism: $(K, M_{\text{min}}, G, C)$ State Machine
Managed by `scripts/stall_controller.py` and hooked into `deme/expand-deme.metta`:

1. **State Machine States:**
   - `BASE`: Operates at $r_{\text{base}} = 14.0$. Tracks generations without improvement in **best-ever raw score**.
   - `RELAXED`: When stall counter reaches $K$, switches to $r_{\text{relax}} = 100.0$ for a minimum window of $M_{\text{min}}$ generations.
   - `COOLDOWN`: After the relaxed window expires, restores $r_{\text{base}}$ for $C$ generations before relaxation can be triggered again.

2. **Breakthrough Grace Period ($G$):**
   If a raw breakthrough occurs during the `RELAXED` window, the controller grants a grace period of $G$ extra generations (`relaxed_gens_remaining = max(relaxed_gens_remaining, G)`), allowing the search to fully exploit the relaxed landscape before cooling down.

3. **Metapopulation Rescoring & Ordered Set Invariant:**
   Stored penalized scores become stale when the ratio switches. If not rescored, existing exemplars retain low-ratio penalized scores while new candidates receive high-ratio scores.
   - At each ratio switch, `(rescoreMetapop $metaPop $nextRatio)` recalculates penalized fitness for every exemplar:
     $$\text{penScore} = \text{raw} - \frac{\text{cpxy}}{r_{\text{next}}}$$
   - The metapopulation is fully re-sorted via `(OS.insert compareExemplar ...)`.
   - Hill-climbing's scoring context `$truthTableBScore` is rebuilt via `(createTruthTableBScore $nextRatio $itable)` so that neighborhood search instantly adopts the active ratio.

4. **Strict Fairness Guarantee:**
   Regardless of the active ratio at termination, all final returned candidates in `FinalResult` are rescored back to $r_{\text{base}}$ in `moses/demo-problems.metta`.

---

## 6. Experimental Benchmark Suite

The intervention is evaluated using a 5-arm pre-registered benchmark across 20 paired seeds on `parity4`, `majority5`, and `parity5` (300 runs total):

| Arm | Description | Parameters |
|:---|:---|:---|
| `static_14` | Baseline | $r = 14.0$, `stallRelaxationMode=False` |
| `static_100` | Static Upper Bound | $r = 100.0$, `stallRelaxationMode=False` |
| `stall_relax_K3` | Dynamic Stall ($K=3$) | $r_{\text{base}}=14, r_{\text{relax}}=100, K=3, M_{\text{min}}=3, G=2, C=3$ |
| `stall_relax_K5` | Dynamic Stall ($K=5$) | $r_{\text{base}}=14, r_{\text{relax}}=100, K=5, M_{\text{min}}=3, G=2, C=3$ |
| `trigger_only_ctrl` | Rescore Negative Control | $r_{\text{base}}=14, r_{\text{relax}}=14, K=3, M_{\text{min}}=3, G=2, C=3$ |

**Pre-Registered Evaluation Metrics:**
- **Primary Metric:** Best-ever raw score at termination (paired Wilcoxon signed-rank test against `static_14`).
- **Breakout Rate:** McNemar's exact test for proportion of seeds reaching breakout criteria.
- **Overfitting & Bloat Checks:** Mean literal count of final candidates.
- **Computational Overhead:** Total evaluations (`OptimizedDeme`), wall-clock runtime, and fraction of generations relaxed.

---

## 7. CLI Flags & Hyperparameters

| Flag | Default | Description |
|:---|:---:|:---|
| `--stallRelaxationMode=<str>` | `False` | Controller mode: `False` (static), `dynamic`, or `trigger_only`. |
| `--baseComplexityRatio=<float>` | `14.0` | Baseline parsimonious complexity ratio. |
| `--relaxedComplexityRatio=<float>` | `100.0` | Relaxed complexity ratio triggered on stall. |
| `--stallThresholdK=<int>` | `3` | Number of non-improving generations before relaxation triggers. |
| `--relaxWindowMinM=<int>` | `3` | Minimum consecutive generations to hold relaxed ratio. |
| `--relaxGraceG=<int>` | `2` | Additional generations granted when raw score improves during relaxation. |
| `--relaxCooldownC=<int>` | `3` | Cooldown generations at $r_{\text{base}}$ before relaxation can re-trigger. |
| `--maxRevisits=<int>` | `1` | Maximum times any canonical exemplar tree can be expanded. |
| `--permPolarityMode=<str>` | `classic` | Permutation generator mode: `classic` or `symmetric`. |
| `--logicalPermRatio=<float>` | `1.0` | Clause expansion sampling budget multiplier. |
| `--complexityRatio=<float>` | `3.5` | Standard complexity penalty divisor (when relaxation is disabled). |
| `--problem=<str>` | — | Benchmark problem: `parity3`, `parity4`, `parity5`, `majority3`, `majority5`, `majority7`, `mux3`, `mux6`, `disjunction3`. |

---

## 8. Verification & Experiment Execution

```sh
# 1. Run Stall Controller unit tests
python3 scripts/test_stall_controller_unit.py

# 2. Run end-to-end integration test (parity4, dynamic stall switching)
python3 scripts/test_dynamic_stall_e2e.py

# 3. Run full 5-arm benchmark sweep (resumable, saves to stall_relaxation_results.json)
python3 scripts/run_stall_relaxation_experiment.py

# 4. Analyze results and compute paired statistical significance
python3 scripts/analyze_stall_relaxation.py
```

