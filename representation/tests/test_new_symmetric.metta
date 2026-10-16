!(import! &self ../../parameters/registry)
!(import! &self ../../parameters/defaults)
!(import! &self ../../utilities/lazy-random-selector)
!(import! &self ../../utilities/general-helpers)
!(import! &self ../../utilities/list-methods)
!(import! &self ../../scoring/boolean-ops)

(= (genUnorderedPairs ()) ())
(= (genUnorderedPairs $xs)
   (if (== $xs ())
       ()
       (let* (($x (car-atom $xs))
              ($rest (cdr-atom $xs))
              ($pairsWithX (map-atom $rest $y ($x $y))))
           (concatT $pairsWithX (genUnorderedPairs $rest)))))

(= (emitFourSignVariants $op $a $b)
   ((quote ($op $a $b))
    (quote ($op $a (NOT $b)))
    (quote ($op (NOT $a) $b))
    (quote ($op (NOT $a) (NOT $b)))))

(= (emitAllPairVariants $op ()) ())
(= (emitAllPairVariants $op $pairs)
   (if (== $pairs ())
       ()
       (let* (($pair (car-atom $pairs))
              ($rest (cdr-atom $pairs))
              (($a $b) $pair)
              ($four (emitFourSignVariants $op $a $b)))
           (concatT $four (emitAllPairVariants $op $rest)))))

(= (sampleFromList $list $k)
   (let $total (length $list)
      (if (>= $k $total)
          $list
          (if (<= $k 0)
              ()
              (let* (($upper (- $total 1))
                     ($indices (lazyRandomSelector 0 $upper $k)))
                 (map-atom $indices $idx (index-atom $list $idx)))))))

;; Test 1: unordered pairs for 4 variables
!(assertEqual (length (genUnorderedPairs (X1 X2 X3 X4))) 6)
!(assertEqual (genUnorderedPairs (X1 X2 X3 X4)) ((X1 X2) (X1 X3) (X1 X4) (X2 X3) (X2 X4) (X3 X4)))

;; Test 2: all four sign variants for each pair
!(let $allClauses (unique-atom (emitAllPairVariants AND (genUnorderedPairs (X1 X2 X3 X4))))
   (assertEqual (length $allClauses) 24))

;; Test 3: sampling from list
!(py-call (random.seed 42))
!(let* (($allClauses (unique-atom (emitAllPairVariants AND (genUnorderedPairs (X1 X2 X3 X4)))))
        ($sampled4 (sampleFromList $allClauses 4))
        ($sampled24 (sampleFromList $allClauses 24))
        ($sampled30 (sampleFromList $allClauses 30)))
   (and (assertEqual (length $sampled4) 4)
        (assertEqual (length $sampled24) 24)
        (assertEqual (length $sampled30) 24)))

!(println! "All new symmetric generator tests passed!")
