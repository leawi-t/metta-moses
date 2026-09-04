# M3: Metapopulation Initialization Experiments

This directory contains the code, data, and analysis scripts for the M3 experiments on Metapopulation Initialization in MeTTa-MOSES.

## The Problem
Historically, the \metta-moses\ repository initialized the metapopulation using a pure \oulette\ selection policy. While this works when the seed pool contains a single \	rue\ program, it causes a severe initialization collapse when the seed pool contains multiple complex seeds (such as full-width n-ary \AND/OR\ trees or \NOT\ structures). Because complex seeds inherently score higher in their initial evaluations due to partial structural matches, they capture >99.8% of the selection probability mass in Generation 1. This starves foundational seeds (like \	rue\ or binary pairs) of any early exploration, resulting in premature convergence and depressed final scores.

## The Solution
This experiment introduces and tests a new initialization policy: \ootstrap\.
- \initPolicy = roulette\ (Default): The legacy behavior.
- \initPolicy = bootstrap\: Guarantees that every seed in the provided seed pool is allocated its own private Deme and is forcefully expanded exactly once (for one generation) before being merged into the global metapopulation.

## Reproducibility and Data Provenance

The data contained in \data/bootstrap_n30/\ was generated via Python-based code injection over an earlier commit. This method was necessary because the CLI arguments \--pool\ and \--initPolicy\ were not yet wired into the main parameters registry in \moses.metta\. 

To accurately reproduce these exact numbers, we used \scripts/run_decisive_bootstrap.py\, which patches the codebase with the \ootstrapDemes\ helper functions and runs the experiment across 30 seeds deterministically.

### Data
- \data/bootstrap_n30/n_roulette_n30/\: Control run using legacy probability-based selection.
- \data/bootstrap_n30/n_bootstrap_n30/\: Experimental run using the exact same code but with deterministic bootstrap seed expansion.

## Statistical Proof
In a 30-seed rigorous benchmark on \parity3\, using the \pairs_nary\ pool:
- \oulette\ mean score: -3.2857
- \ootstrap\ mean score: -3.0238
- Mean paired improvement: +0.2619 (Wilcoxon p-value = 0.00025, p < 0.001).

Bootstrap definitively mitigates the probability starvation bug with no performance overhead on clean seed sets.
