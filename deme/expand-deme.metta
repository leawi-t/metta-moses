;; WARN: This code might be generating knobs out of order. Check if the knob map returned from the representation building preserves the order of knob creation.
(= (createInitialInstance $dscMp)
   (let* (
          ($knobs (Map.values $dscMp))
          ($defaults (List.map getKnobDefault $knobs))
          ($finalDefaults (List.map second $defaults))
         )
         $finalDefaults))

;; Recursively optimizes each deme in a list using the provided optimizer function.
;; Params:
;;   (List Deme): The list of demes to optimize.
;;   $context: The scoring context - either TruthTableBScore or tuple ($nGames $opponentPolicy)
;;   $inst: The initial instance for optimization.
;;   $optimize: The optimizer function to apply to each deme.
;;  Returns: (List Deme): A new list where each deme has been optimized.
; (: optimizeDemes (-> (List Deme) $context Instance $optimize (Instance Deme $state)))
;; Game strategy version - unpacks tuple with target score
;; Strategy version - unpacks game parameters and calls hillClimbing with mkParams
(= (optimizeDemes $deme ($nGames $complexityRatio $targetCScore) $inst $optimize)
   ($optimize $deme $targetCScore $inst (mkParams applyStrategyBasedScore ($nGames $complexityRatio))))
;; Boolean version - passes context as-is
(= (optimizeDemes $deme $context $inst $optimize)
   ($optimize $deme $context $inst))

;; Extracts default specification from a knob
; (: getKnobDefault (-> $knob Number))
;; (= (getKnobDefault (mkLSK (mkDiscKnob $multip $curr (mkDiscSpec $def) $dis))) $def)
;; (= (getKnobDefault (mkSSK (mkDiscKnob $knob $multip $curr (mkDiscSpec $def) $dis))) $def)

;; Runs one deme-creation and optimization step, then merges the optimized deme into the metapopulation.
;; Params:
;;   $metaPop: The current metapopulation.
;;   $nExpansion: Expansion count or deme index.
;;   $nDeme: Number of demes to create.
;;   $truthTableBScore: TruthTableBScore
;;   $optimize: Optimizer function (e.g., hill climbing).
;;   $nEval: Maximum number of evaluations.
;;   $maxCandsPerDeme: Maximum candidates per deme.
;;   $minPoolSize: Minimum deme size to retain.
;;   $complexityTemperature: Parameter for score range in trimming.
;;   $itable: The input table.
;;   $nToKeep: Target size for resized metapopulation.
;;   $capCoef: Capacity coefficient for resizing.
;;   $genCount: Generation count for resizing.
;; Returns:
   ;;   $updatedMetaPop: Updated metapopulation with the new optimized deme merged in.
; (: expandDeme (-> (OS (Exemplar $a)) Number Number Bool Symbol (TruthTableBScore $a) (-> Deme (TruthTableBScore $a) Instance $Scorer (Instance Deme $state)) $Scorer Number Number Number Number (ITable $a) Number Number Number (OS (Exemplar $a))))
(= (expandDeme $metaPop $nExpansion $nDeme $prune-exemplar $fs-algo $truthTableBScore $optimize $itable $scorerType)
(let*
   (
    ($exemplar (selectExemplar $metaPop))
    ($tree (getExemplarTree $exemplar)) 
    ($score (getExemplarCscore $exemplar))
    ($raw (getScore $score))
    ($pen (getPenScore $score))
    ($_rec (py-call (visited_tracker.record_visit (preOrder $tree))))
    ($_ (py-call (logger_helper.log_exemplar $nExpansion (preOrder $tree) $raw $pen)))
    ($_ (println! (SelectedTree: (preOrder $tree))))
    ;; ($_ (println! "creating deme IDs"))
    ($demeIds (createDemeIds $nExpansion $nDeme))
    ;; ($_ (println! $demeIds))
    ; ($argLabels (getArgLabels $itable))
    ;; ($_ (println! "Creating Deme"))
    ($demes (createDeme $nDeme $demeIds $tree $itable $fs-algo $prune-exemplar () $scorerType))
    )
    (map-atom $demes $deme (expandDemeHelper $deme $truthTableBScore $optimize))
   ))

;; Overloaded version for game strategy domain - 8 parameters
(= (expandDeme $metaPop $nExpansion $nDeme $nGames $complexityRatio $targetCScore $optimize)
   (let*
      (
         ($exemplar (trace! "Selecting Exemplar" (selectExemplar $metaPop)))
         ($tree (trace! "getting exemplar tree" (getExemplarTree $exemplar)))
         ($demeIds (trace! "creating deme IDs" (createDemeIds $nExpansion $nDeme)))
         ($demes (trace! "Creating Deme" (createDeme $nDeme $demeIds $tree)))
         ($gameContext ($nGames $complexityRatio $targetCScore))
      )
      (map-atom $demes $deme (expandDemeHelper $deme $gameContext $optimize))))

;; Unified helper for both Boolean and Strategy domains
;; Optimizes each deme in the list using the provided optimizer and context
;; Params:
;;   $deme: Deme to optimize
;;   $context: Scoring context (ITable for Boolean, tuple for Strategy)
;;   $optimize: Optimizer function
;; Returns: Optimized deme with scored instances
(= (expandDemeHelper (mkDeme (mkRep (mkKbMap (mkDscMp $dscKbMp)) $updatedTree) $sInstList $demeId) $context $optimize)
(let*
(
    ($lengthOfDscKbMp (Map.length $dscKbMp))
    ;; ($generatedList (List.generate $lengthOfDscKbMp 0))
    ($generatedList (createInitialInstance $dscKbMp))
    ($_ (println! (GeneratedList: $generatedList)))
    ($deme (mkDeme (mkRep (mkKbMap (mkDscMp $dscKbMp)) $updatedTree) $sInstList $demeId))
    ;; ($_ (println! (Rep: (mkRep (mkKbMap (mkDscKbMp $dscKbMp) (mkDscMp $dscMp)) $updatedTree))))
    ;; ($_ (println! "Optimizing Deme"))
    (($inst $optimDeme $state) (optimizeDemes $deme $context (mkInst $generatedList) $optimize))
)
$optimDeme
))
;; The main loop
;; Takes 2 termination criterias:
;;     - $maxGen : how many times we want the loop to run
;;     - $maxScore : the maximum *raw* score we want the top Examplar to reach.
;;                   This is a scalar (Number), matching classic MOSES'
;;                   `score_t target_score = c_scorer.best_possible_score()`.
;;                   For clean boolean tables it's 0. The complexity penalty
;;                   is applied per-candidate during scoring, separate from
;;                   this termination check.
; (: runMoses (-> Number Number (OS (Exemplar $a)) Number Number $Context $Optimize (OS (Exemplar $a))))
;; TODO: $nEval isn't being used. Increase it so that it works as expected.
;; To enable that, we may need to change our termination condition so that the generation is equivalent to the number of expansion as well.
(= (registerMetapopSurvivors ()) ())
(= (registerMetapopSurvivors (cons $ex $rest))
   (let* (($tree (getExemplarTree $ex))
          ($_ (py-call (logger_helper.register_metapop_exemplar (preOrder $tree)))))
      (registerMetapopSurvivors $rest)))

(= (handleStallSwitch $switched $metaPop $context)
   (if (== $switched 1)
       (let*
         (
           ($nextRatio (py-call (stall_controller.get_current_ratio)))
           ($nextState (py-call (stall_controller.get_current_state)))
           ($_setParam (set-param complexityRatio $nextRatio))
           ($_print (println! (RatioSwitchedTo: $nextRatio State: $nextState)))
           ($rescoredMetaPop (rescoreMetapop $metaPop $nextRatio))
           ($nextContext (case $context
                           ((($prune-exemplar $fs-algo $truthTableBScore $itable)
                             ($prune-exemplar $fs-algo (createTruthTableBScore $nextRatio $itable) $itable))
                            (($nGames $opponentPolicy $complexityRatio)
                             ($nGames $opponentPolicy $nextRatio)))))
         )
         ($rescoredMetaPop $nextContext))
       ($metaPop $context)))

;; The number of expansions in the open cog classic is equivalent to the number of deme expansions. That looks like the same thing we are doing here but not sure.
(= (runMoses $maxGen $maxScore $metaPop $nExpansion $nDeme $context $optimize)
(if (== $maxGen 0)
    (let* (($_ (py-call (logger_helper.set_termination_reason "max_gen_reached"))))
      (if (<= (param maxCandOutput) (OS.length $metaPop))
          (let $topCandidates (OS.getTopN (param maxCandOutput) $metaPop) $topCandidates)
          $metaPop))
    (let*
     (
       ($_ (println! (Generation $maxGen)))
        ($optimizedDemes (case $context
                        ((($prune-exemplar $fs-algo $truthTableBScore $itable) (trace! "expand  deme returnn" (expandDeme $metaPop $maxGen $nDeme $prune-exemplar $fs-algo $truthTableBScore $optimize $itable mi)))
                        (($nGames $opponentPolicy $complexityRatio) (trace! "expand deme return" (expandDeme $metaPop $maxGen $nDeme $nGames $opponentPolicy $complexityRatio $maxScore $optimize))))))
       (((mkDeme $rep $sInst $demeId)) $optimizedDemes)
       ($_ (println! (OptimizedDeme: (List.length (second $sInst)))))
       ($updatedMetaPop (case $context
                        ((($prune-exemplar $fs-algo $truthTableBScore $itable) (trace! "Merging Deme" (mergeDemes $optimizedDemes $itable $metaPop)))
                        (($nGames $opponentPolicy $complexityRatio) (trace! "Merging Deme" (mergeDemes $optimizedDemes ($nGames $opponentPolicy) $metaPop))))))
       (($bestRawInMetapop $bestRawComplexity) (getMetapopBestRawInfo $updatedMetaPop))
       ($top (OS.getByIdx 0 $updatedMetaPop))
       ($topScore (getExemplarCscore $top))
       ($topPen (getPenScore $topScore))
       ($_surv (registerMetapopSurvivors $updatedMetaPop))
       ($_ (py-call (logger_helper.finalize_generation_stats $maxGen $bestRawInMetapop $bestRawComplexity $topPen)))
       ;; ($_ (println! (topscore: $topScore)))
       ;; ($_ (println! (Top: $topScore Max: $maxScore (cScore>= $topScore $maxScore))))
       ($stallMode (param stallRelaxationMode))
       ($switched (if (or (== $stallMode False) (== $stallMode ()))
                      0
                      (py-call (stall_controller.step_controller $maxGen $bestRawInMetapop))))
       (($nextMetaPop $nextContext) (handleStallSwitch $switched $updatedMetaPop $context))
       ($nothing (clearSpace &treeSpace))
       ($_ (cut)) ;; INFO: This cut speeds things up. Don't remove it.
       ($_ (println! ""))
      )
 ;; Match classic semantics: compare the raw behavioural score against the
 ;; scalar `$maxScore`. The Cscore's complexity / penalty fields are
 ;; consulted elsewhere when ranking candidates but not at termination.
 (if (>= (getScore $topScore) $maxScore)
         (let* (($_ (py-call (logger_helper.set_termination_reason "solved"))))
           (if (<= (param maxCandOutput) (OS.length $nextMetaPop))
               (OS.getTopN (param maxCandOutput) $nextMetaPop)
               $nextMetaPop))
         (runMoses (- $maxGen 1) $maxScore $nextMetaPop $nExpansion $nDeme $nextContext $optimize)))))



;; Some helpers specific to final testing
(= (mapG $f $xs) (map-atom $xs $f))

(= (printExemplar (mkExemplar $tree $demeId $cscore $bscore)) (println! (Tree: (preOrder $tree) CScore: $cscore Bscore: $bscore)))
(= (cleanedExemplar (mkExemplar $tree $demeId $cscore (mkBScore $bscore))) ((preOrder $tree) (List.sum $bscore)))
(= (cleanedExemplars ()) ())
(= (cleanedExemplars (cons (mkExemplar $tree $demeId $cscore (mkBScore $bscore)) $rest))
   (cons ((preOrder $tree) (List.sum $bscore)) (cleanedExemplars $rest)))
(= (cleanedExemplars (cons $x $rest))
   (cleanedExemplars $rest))
(= (cleanedExemplars $xs) (mapG cleanedExemplar $xs))

(= (printInstance (mkInst $inst)) (println! (List.listToExpr $inst)))
