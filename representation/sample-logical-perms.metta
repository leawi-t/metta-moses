;; Permutation sampling for logical / strategy knob building. Only ~arity random
;; pairs/triplets are ever needed, so rather than enumerating the whole list we
;; map each random index straight to its pair/triplet (pairAt / tripletAt),
;; mirroring classic build_knobs::sample_logical_perms.

(= (intDiv $a $b) (floor-math (/ $a $b)))

;; $i-th ordered pair ($a $b), $a != $b, over {0 .. $n-1} in lexicographic order
(= (pairAt $n $i)
    (let* (($d (- $n 1))
           ($a (intDiv $i $d))
           ($j (% $i $d))
           ($b (if (< $j $a) $j (+ $j 1))))
        ($a $b)))

;; $i-th ordered triplet of distinct ($x $y $z) over {0 .. $n-1}; each $x owns a
;; block of (n-1)(n-2) triplets whose ($y $z) come from pairAt over the rest
(= (tripletAt $n $i)
    (let* (($m (- $n 1))
           ($per (* $m (- $m 1)))
           ($x (intDiv $i $per))
           ($k (% $i $per))
           (($p $q) (pairAt $m $k))
           ($y (if (< $p $x) $p (+ $p 1)))
           ($z (if (< $q $x) $q (+ $q 1))))
        ($x $y $z)))

;; genPairs / genTriplet: deterministic full enumerations, kept as utilities
;; (: genPairs (-> Expression Expression))
(= (genPairs $list) (genPairsLoop $list $list))

(= (genPairsLoop $xs $full)
    (if (== $xs ())
        ()
        (let* (($x (car-atom $xs))
               ($rest (cdr-atom $xs)))
            (pairWith $x $full (genPairsLoop $rest $full)))))

(= (pairWith $x $ys $tail)
    (if (== $ys ())
        $tail
        (let* (($y (car-atom $ys))
               ($rest (cdr-atom $ys)))
            (if (== $x $y)
                (pairWith $x $rest $tail)
                (cons-atom ($x $y) (pairWith $x $rest $tail))))))

;; (: genTriplet (-> Expression Expression))
(= (genTriplet $list) (genTripletLoop $list (genPairs $list)))

(= (genTripletLoop $xs $pairs)
    (if (== $xs ())
        ()
        (let* (($x (car-atom $xs))
               ($rest (cdr-atom $xs)))
            (tripletWith $x $pairs (genTripletLoop $rest $pairs)))))

(= (tripletWith $x $pairs $tail)
    (if (== $pairs ())
        $tail
        (let* (($p (car-atom $pairs))
               ($rest (cdr-atom $pairs))
               (($y $z) $p))
            (if (and (!= $x $y) (!= $x $z))
                (cons-atom ($x $y $z) (tripletWith $x $rest $tail))
                (tripletWith $x $rest $tail)))))

;; genUnorderedPairs -> all distinct unordered pairs (a, b) from argLabels with a before b
(= (genUnorderedPairs ()) ())
(= (genUnorderedPairs $xs)
   (if (== $xs ())
       ()
       (let* (($x (car-atom $xs))
              ($rest (cdr-atom $xs))
              ($pairsWithX (map-atom $rest $y ($x $y))))
           (concatT $pairsWithX (genUnorderedPairs $rest)))))

;; emitFourSignVariants -> for an unordered pair (a, b), emit all four sign patterns
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

;; sampleFromList -> uniformly sample k elements without replacement from list
(= (sampleFromList $list $k)
   (let $total (length $list)
      (if (>= $k $total)
          $list
          (if (<= $k 0)
              ()
              (let* (($upper (- $total 1))
                     ($indices (lazyRandomSelector 0 $upper $k)))
                 (map-atom $indices $idx (index-atom $list $idx)))))))

;; getArgsClassic -> original asymmetric pair generator
(= (getArgsClassic $swapedOp $n $picked $argLabels)
    (map-atom $picked $i
        (let* ((($a $b) (pairAt $n $i))
               ($1 (index-atom $argLabels $a))
               ($2 (index-atom $argLabels $b)))
            (if (< $b $a)
                (quote ($swapedOp $2 $1))
                (quote ($swapedOp (NOT $1) $2))))))

;; getArgs -> defaults to getArgsClassic for backward compatibility
(= (getArgs $swapedOp $n $picked $argLabels)
   (getArgsClassic $swapedOp $n $picked $argLabels))

(= (getLogicalPermRatio)
   (let $r (param logicalPermRatio)
        (if (or (== $r ()) (== (get-metatype $r) Expression))
            1.0
            $r)))

(= (getPermPolarityMode)
   (let $m (param permPolarityMode)
        (if (or (== $m ()) (== (get-metatype $m) Expression))
            classic
            $m)))

;; sampleLogicalPerms -> generate logical permutations for boolean expressions
(= (sampleLogicalPerms $op $arity $argLabels)
   (let* (($swapedOp (swapAndOr $op))
          ($mode (getPermPolarityMode)))
      (if (== $mode symmetric)
          (sampleLogicalPermsSymmetric $swapedOp $arity $argLabels)
          (sampleLogicalPermsClassic $swapedOp $arity $argLabels))))

(= (sampleLogicalPermsClassic $swapedOp $arity $argLabels)
    (let* (($ratio (getLogicalPermRatio))
           ($rawN (floor-math (* $arity $ratio)))
           ($maxPoss (* $arity (- $arity 1)))
           ($nPairs (if (> $rawN $maxPoss) $maxPoss $rawN)))
        (if (<= $nPairs 1)
            (let $arg (car-atom $argLabels) (quote ($arg (NOT $arg))))
            (let* (($upperbound (- $maxPoss 1))
                   ($picked (lazyRandomSelector 0 $upperbound $nPairs))
                   ($perms (getArgsClassic $swapedOp $arity $picked $argLabels)))
               (concatT $argLabels $perms)))))

(= (sampleLogicalPermsSymmetric $swapedOp $arity $argLabels)
    (let* (($ratio (getLogicalPermRatio))
           ($pairs (genUnorderedPairs $argLabels))
           ($rawClauses (emitAllPairVariants $swapedOp $pairs))
           ($allClauses (unique-atom $rawClauses))
           ($totalClauses (length $allClauses))
           ($rawN (floor-math (* $arity $ratio)))
           ($nPairs (if (> $rawN $totalClauses) $totalClauses $rawN)))
        (if (<= $nPairs 1)
            (let $arg (car-atom $argLabels) (quote ($arg (NOT $arg))))
            (let $perms (sampleFromList $allClauses $nPairs)
               (concatT $argLabels $perms)))))




;; getMoveArgs -> generate move expressions for the picked triplet indices
;; Params:
;;          $op: move operator (PRIORITIZED-OR)
;;          $n: number of move labels (index space {0 .. $n-1})
;;          $picked: list of picked triplet idxs
;;          $moveLabels: list of move labels (playcenter, playcorner, etc.)
;; (: getMoveArgs (-> Atom Number Expression Expression Expression))
(= (getMoveArgs $op $n $picked $moveLabels)
    (map-atom $picked $i
        (let* ((($a $b $c) (tripletAt $n $i))
               ($move1 (index-atom $moveLabels $a))
               ($move2 (index-atom $moveLabels $b))
               ($move3 (index-atom $moveLabels $c)))
            ($op $move1 $move2 $move3))))

;; sampleStrategyPerms -> generate strategy permutations for game strategy evolution
;; Params:
;;          $op: the strategy operator (PRIORITIZED-OR)
;;          $arity: the number of moves in the strategy sequence
;;          $moveLabels: list of move labels (playcenter, playblock, playcorner, etc.)
;; Returns:
;;          Union of original moves with alternative move strategy expressions
;; (: sampleStrategyPerms (-> Atom Number Expression Expression))
(= (sampleStrategyPerms $op $arity $moveLabels)
    (let* (($n (length $moveLabels))
           ($nPairs $arity))
        (if (<= $nPairs 1)
            ($op (car-atom $moveLabels))
            (let* (($upperbound (- (* $n (* (- $n 1) (- $n 2))) 1))
                   ($picked (lazyRandomSelector 0 $upperbound $nPairs))
                   ($perms (getMoveArgs $op $n $picked $moveLabels)))
               $perms))))
