!(callPredicate (Predicate (py_add_lib_dir "scripts" first)))
!(import! &self utilities/general-helpers)
!(import! &self utilities/list-methods)
!(import! &self utilities/pair)

!(import! &self reduct/boolean-reduct/rte-helpers)
!(import! &self reduct/boolean-reduct/cut-unnecessary-or)
!(import! &self reduct/boolean-reduct/cut-unnecessary-and)
!(import! &self reduct/boolean-reduct/n-ary-propagate-not)
!(import! &self reduct/boolean-reduct/delete-inconsistent-handle)
!(import! &self reduct/boolean-reduct/zero-constraint-subsumption)
!(import! &self reduct/boolean-reduct/one-constraint-subsumption)
!(import! &self reduct/boolean-reduct/promote-common-constraints)
!(import! &self reduct/boolean-reduct/n-ary-gather-junctors)
!(import! &self reduct/boolean-reduct/reduce-to-elegance)
!(callPredicate (Predicate (consult "moses/tests/rte-helpers-fast.pl")))
!(import! &self utilities/tree)


(= (test-single-tree $idx)
   (let* (
          ($rawStr (py-call (reduction_validator.get_raw_tree $idx)))
          ($permStr (py-call (reduction_validator.get_perm_tree $idx)))
          ($rawTree (buildTree (parse $rawStr)))
          ($permTree (buildTree (parse $permStr)))
          ;; 1. Clean raw tree
          ($red1 (cleanTree $rawTree))
          ;; 2. Clean again (idempotence)
          ($red2 (cleanTree $red1))
          ;; 3. Clean permuted tree
          ($permRed (cleanTree $permTree))
          ;; 4. Strings for Python validator
          ($red1Str (py-call (str (preOrder $red1))))
          ($red2Str (py-call (str (preOrder $red2))))
          ($permRedStr (py-call (str (preOrder $permRed))))
          ($_ (py-call (reduction_validator.record_validation $rawStr $red1Str $red2Str $permRedStr)))
         )
      $red1Str))


(= (run-item-loop $i $max)
   (if (> $i $max)
       (py-call (reduction_validator.summarize_results))
       (let* (
              ($_ (test-single-tree $i))
              ($next (+ $i 1))
             )
          (run-item-loop $next $max))))

!(run-item-loop 1 50)
