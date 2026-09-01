;; ============================================================
;; Bootstrap Smoke Test
;; Verifies that the new initPolicy and seedPool parameters
;; parse correctly and run without syntax errors.
;; ============================================================

!(import! &self ../moses.metta)

;; Set parameters for a tiny smoke test
!(set-param maxGen 2)
!(set-param nDeme 1)
!(set-param problem parity3)

;; Test 1: Legacy Roulette
!(set-param initPolicy roulette)
!(set-param seedPool legacy)
!(println! "--- Running Legacy Roulette ---")
!(moses)

;; Test 2: Bootstrap with Pairs
!(set-param initPolicy bootstrap)
!(set-param seedPool pairs)
!(println! "--- Running Bootstrap Pairs ---")
!(moses)

!(println! "Bootstrap Smoke Test Completed Successfully!")
