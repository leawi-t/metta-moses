!(import! &self ../../parameters/registry)
!(import! &self ../../parameters/defaults)
!(import! &self ../../utilities/lazy-random-selector)
!(import! &self ../../utilities/general-helpers)
!(import! &self ../../utilities/list-methods)
!(import! &self ../../representation/sample-logical-perms)
!(import! &self ../../scoring/boolean-ops)
!(import! &self ../../scoring/bscore)

!(set-param permPolarityMode symmetric)
!(set-param logicalPermRatio 6.0)

;; With arity 4 and logicalPermRatio 6.0, all 24 pairwise clauses are sampled:
;; 4 input variables + 24 clauses = 28 total elements
!(assertEqual (length (sampleLogicalPerms AND 4 (X1 X2 X3 X4))) 28)
!(assertEqual (length (sampleLogicalPerms OR 4 (X1 X2 X3 X4))) 28)

!(println! "Symmetric permutation tests passed successfully!")
