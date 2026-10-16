import itertools
from pathlib import Path

def generate_metta_cscore_test():
    combos = list(itertools.combinations(range(1, 8), 4))
    clauses = ["(AND " + " ".join(f"X{v}" for v in c) + ")" for c in combos]
    perfect_maj7_str = "(quote (OR " + " ".join(clauses) + "))"
    
    plateau_maj7_str = (
        "(quote (OR (AND (OR (AND (OR (AND X2 X6) X5) X4) (AND X3 X7) X1) (OR (AND X2 X6) (AND X3 X7) (AND X4 X5))) "
        "(AND (OR (AND (OR (AND X1 X3) (AND X4 X6)) X7) (AND X2 X6)) (OR (AND X1 X3) X5)) "
        "(AND (OR (AND X2 X5) (AND X3 X6)) (OR (AND X3 X6) X1) (OR (AND X2 X5) (AND X4 X7)))))"
    )
    
    content = f''';; Test getCscore on Perfect DNF vs Plateau Tree across complexity ratios in MeTTa
!(import! &self utilities/general-helpers)
!(import! &self parameters/registry)
!(import! &self parameters/defaults)
!(import! &self utilities/list-methods)
!(import! &self utilities/pair)
!(import! &self utilities/tree)
!(import! &self scoring/cacheSpace)
!(import! &self scoring/fitness)
!(import! &self scoring/boolean-ops)
!(import! &self scoring/bscore)
!(import! &self scoring/cscore)
!(import! &self moses/demo-problems)

(= (perfectMaj7Tree) (buildTree {perfect_maj7_str}))
(= (plateauMaj7Tree) (buildTree {plateau_maj7_str}))

!(println! "============================================================")
!(println! "METTA: GETCSCORE COMPARISON FOR MAJORITY-7")
!(println! "============================================================")

!(println! ("Complexity of Perfect Maj7 DNF: " (treeComplexity (perfectMaj7Tree))))
!(println! ("Complexity of Plateau Maj7 Tree: " (treeComplexity (plateauMaj7Tree))))

!(println! "")
!(println! "--- complexityRatio = 3.5 ---")
!(let $score (getCscore (majority7) (perfectMaj7Tree) 3.5 &bscoreCache) (println! ("Perfect Maj7 DNF cscore: " $score)))
!(let $score (getCscore (majority7) (plateauMaj7Tree) 3.5 &bscoreCache) (println! ("Plateau Maj7 Tree cscore: " $score)))

!(println! "")
!(println! "--- complexityRatio = 7.0 ---")
!(let $score (getCscore (majority7) (perfectMaj7Tree) 7.0 &bscoreCache) (println! ("Perfect Maj7 DNF cscore: " $score)))
!(let $score (getCscore (majority7) (plateauMaj7Tree) 7.0 &bscoreCache) (println! ("Plateau Maj7 Tree cscore: " $score)))

!(println! "")
!(println! "--- complexityRatio = 14.0 ---")
!(let $score (getCscore (majority7) (perfectMaj7Tree) 14.0 &bscoreCache) (println! ("Perfect Maj7 DNF cscore: " $score)))
!(let $score (getCscore (majority7) (plateauMaj7Tree) 14.0 &bscoreCache) (println! ("Plateau Maj7 Tree cscore: " $score)))

!(println! "")
!(println! "--- complexityRatio = 100000.0 (large, effectively 0 penalty) ---")
!(let $score (getCscore (majority7) (perfectMaj7Tree) 100000.0 &bscoreCache) (println! ("Perfect Maj7 DNF cscore: " $score)))
!(let $score (getCscore (majority7) (plateauMaj7Tree) 100000.0 &bscoreCache) (println! ("Plateau Maj7 Tree cscore: " $score)))
'''
    with open("/home/nonplds/projects/metta-projects/metta-moses-representation/test_cscore_maj7.metta", "w") as f:
        f.write(content)
    print("Generated test_cscore_maj7.metta")

if __name__ == "__main__":
    generate_metta_cscore_test()
