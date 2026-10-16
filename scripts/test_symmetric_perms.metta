!(import! &self utilities/general-helpers)
!(import! &self utilities/list-methods)
!(import! &self utilities/lazy-random-selector)
!(import! &self representation/sample-logical-perms)
!(import! &self scoring/boolean-ops)
!(import! &self scoring/bscore)

;; Test new symmetric getArgs
(= (getArgsSymmetric $swapedOp $n $picked $argLabels)
    (map-atom $picked $i
        (let* (($p (intDiv $i 2))
               ($m (% $i 2))
               (($a $b) (pairAt $n $p))
               ($1 (index-atom $argLabels $a))
               ($2 (index-atom $argLabels $b)))
            (if (== $m 0)
                (quote ($swapedOp (NOT $1) $2))
                (if (< $a $b)
                    (quote ($swapedOp $1 $2))
                    (quote ($swapedOp (NOT $1) (NOT $2))))))))

;; Full enumeration of all 24 indices for 4 variables
(= (allPickedIndices)
   (quote (0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23)))

!(let* (($labels (quote (X1 X2 X3 X4)))
        ($indices (allPickedIndices))
        ($allClauses (getArgsSymmetric AND 4 $indices $labels))
        ($_ (println! ("Generated clauses count:" (size-atom $allClauses))))
        ($_ (println! ("Sample clauses:" (take 8 $allClauses))))
       )
    (println! "Verification done!"))
