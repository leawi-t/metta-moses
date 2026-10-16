!(callPredicate (Predicate (py_add_lib_dir "scripts" first)))
!(import! &self parameters/registry)
!(import! &self parameters/defaults)
!(import! &self utilities/general-helpers)
!(import! &self utilities/list-methods)
!(import! &self utilities/pair)
!(import! &self utilities/tree)

(= (test-metta-pycall)
   (let* (
     ($_reset (py-call (visited_tracker.reset)))
     ;; 1. Check true
     ($elTrueBefore (py-call (visited_tracker.is_eligible true 1)))
     ($_recTrue (py-call (visited_tracker.record_visit true)))
     ($elTrueAfter (py-call (visited_tracker.is_eligible true 1)))

     ;; 2. Permutation trees via preOrder
     ;; Tree1: (AND X2 X1)
     ($t1 (mkTree (mkNode AND) (cons (mkTree (mkNode X2) ()) (cons (mkTree (mkNode X1) ()) ()))))
     ($po1 (preOrder $t1))
     ($elT1Before (py-call (visited_tracker.is_eligible $po1 1)))
     ($_recT1 (py-call (visited_tracker.record_visit $po1)))
     ($elT1After (py-call (visited_tracker.is_eligible $po1 1)))

     ;; Tree2: (AND X1 X2)
     ($t2 (mkTree (mkNode AND) (cons (mkTree (mkNode X1) ()) (cons (mkTree (mkNode X2) ()) ()))))
     ($po2 (preOrder $t2))
     ;; Since (AND X2 X1) was visited, (AND X1 X2) must be recognized as visited!
     ($elT2 (py-call (visited_tracker.is_eligible $po2 1)))

     ;; 3. Fallback tracking
     ($_fb1 (py-call (visited_tracker.record_fallback)))
     ($_fb2 (py-call (visited_tracker.record_fallback)))
     ($fbCount (py-call (visited_tracker.get_fallback_count)))

     ;; 4. Reset
     ($_reset2 (py-call (visited_tracker.reset)))
     ($fbCountAfterReset (py-call (visited_tracker.get_fallback_count)))
     ($elT2AfterReset (py-call (visited_tracker.is_eligible $po2 1)))
   )
   (TestResults:
     (TrueBefore: $elTrueBefore Expected: 1)
     (TrueAfter: $elTrueAfter Expected: 0)
     (T1Before: $elT1Before Expected: 1)
     (T1After: $elT1After Expected: 0)
     (T2Eligible: $elT2 Expected: 0)
     (FallbackCount: $fbCount Expected: 2)
     (FallbackAfterReset: $fbCountAfterReset Expected: 0)
     (T2AfterReset: $elT2AfterReset Expected: 1))))

!(test-metta-pycall)
