import sys
import os
import subprocess
import shutil
import re
import json
import time
import argparse

os.chdir('/home/nonplds/projects/metta-projects/metta-moses')
FPATH = 'moses/demo-problems.metta'

SEEDS_P = """\
(= (getSeedTrees $itable)
   (cons (mkTree (mkNode true) ())
   (cons (mkTree (mkNode AND) (cons (mkTree (mkNode X1) ()) (cons (mkTree (mkNode X2) ()) ())))
   (cons (mkTree (mkNode OR)  (cons (mkTree (mkNode X1) ()) (cons (mkTree (mkNode X2) ()) ())))
   (cons (mkTree (mkNode AND) (cons (mkTree (mkNode X1) ()) (cons (mkTree (mkNode X3) ()) ())))
   (cons (mkTree (mkNode OR)  (cons (mkTree (mkNode X1) ()) (cons (mkTree (mkNode X3) ()) ())))
   ()))))))
"""

SEEDS_N = """\
(= (getSeedTrees $itable)
   (cons (mkTree (mkNode true) ())
   (cons (mkTree (mkNode AND) (cons (mkTree (mkNode X1) ()) (cons (mkTree (mkNode X2) ()) ())))
   (cons (mkTree (mkNode OR)  (cons (mkTree (mkNode X1) ()) (cons (mkTree (mkNode X2) ()) ())))
   (cons (mkTree (mkNode AND) (cons (mkTree (mkNode X1) ()) (cons (mkTree (mkNode X3) ()) ())))
   (cons (mkTree (mkNode OR)  (cons (mkTree (mkNode X1) ()) (cons (mkTree (mkNode X3) ()) ())))
   (cons (mkTree (mkNode AND) (cons (mkTree (mkNode X1) ()) (cons (mkTree (mkNode X2) ()) (cons (mkTree (mkNode X3) ()) ()))))
   (cons (mkTree (mkNode OR)  (cons (mkTree (mkNode X1) ()) (cons (mkTree (mkNode X2) ()) (cons (mkTree (mkNode X3) ()) ()))))
   ()))))))))
"""

HELPERS = """\
(= (scoreSeed $tree $itable $complexityRatio $demeId)
   (let* (
          ($bscore (scoreTree $itable $tree &bscoreCache))
          ($cscore (getCscore $tree $complexityRatio $bscore))
         )
         (mkExemplar $tree $demeId $cscore $bscore)))

(= (evaluateSeeds () $itable $cpxPen $demeId) ())
(= (evaluateSeeds (cons $tree $rest) $itable $cpxPen $demeId)
   (cons (scoreSeed $tree $itable $cpxPen $demeId)
         (evaluateSeeds $rest $itable $cpxPen $demeId)))

(= (getEvaluatedMetaPop $itable $cpxPen $demeId)
   (evaluateSeeds (getSeedTrees $itable) $itable $cpxPen $demeId))
"""

NEW_MOSES_RUN = """(= (moses-run)
   (let*
      (
        ;; Pull every input from the registry up-front so the body
        ;; reads like the historical runDemoProblem.
        ($seed     (param seed))
        ($maxGen   (param maxGen))
        ($nDeme    (param nDeme))
        ($fsAlgo   (param fsAlgo))
        ($optAlgo  (param optAlgo))
        ($problem  (param problem))
        ($initPolicy (param initPolicy))
        ($optimizer (optimizer-for $optAlgo))

        ($srp (py-call (random.seed $seed)))
        ;; genCount feeds the cap-size formula inside resizeMetapop; it
        ;; is conceptually the initial $maxGen and stays constant across
        ;; the recursion, so we seed it once here.
        ($_  (set-param genCount $maxGen))
        ($cpxPen (param complexityRatio))
        ;; Resolve the input table once: a CSV the user passed via
        ;; --inputFile, otherwise the demo problem named by `problem`.
        ($itable (resolve-itable))
        ($truthTableBScore (createTruthTableBScore $cpxPen $itable))
        (($ctor $worstPossibleBScore) (worstPossibleScore $truthTableBScore))
        ($worstPossibleScore (List.sum $worstPossibleBScore))
        ($bestPosssibleScore (getBestPossibleScore))
        ($_ (println! (BestPossibleScore: $bestPosssibleScore)))
        ($initialMetaPop (getEvaluatedMetaPop $itable $cpxPen (mkDemeId "1")))
        
        ($result (if (== $initPolicy bootstrap)
                     (let* (
                             ($nInitialSeeds (List.length $initialMetaPop))
                             ($remainingGens (if (>= $maxGen $nInitialSeeds) (- $maxGen $nInitialSeeds) 0))
                             ($_ (println! (--- Starting Bootstrap Initialization on $nInitialSeeds seeds ---)))
                             ($bootDemes (bootstrapDemes $initialMetaPop 0 $nDeme False $fsAlgo $truthTableBScore $optimizer $itable mi))
                             ($_ (println! (--- Bootstrap Complete. Merging Demes ---)))
                             ($bootMetaPop (mergeDemes $bootDemes $itable $initialMetaPop))
                             ($_ (println! (--- Merging Complete. Starting standard loop ---)))
                           )
                           (runMoses $remainingGens $bestPosssibleScore $bootMetaPop $nInitialSeeds $nDeme (False $fsAlgo $truthTableBScore $itable) $optimizer))
                     (runMoses $maxGen $bestPosssibleScore $initialMetaPop 0 $nDeme (False $fsAlgo $truthTableBScore $itable) $optimizer)))
                     
        ;; ($_ (println! (Result: $result)))
        ($newR (mapG cleanedExemplar $result))
        ($_ (cut)) ;; INFO: This gives few extra seconds performance gain. Do not remove.
      )
      (FinalResult $newR)))"""
      
def apply_condition(seeds_code, helpers_code):
    subprocess.run(["git", "checkout", FPATH], check=True, capture_output=True)
    with open(FPATH, 'r') as f:
        content = f.read()

    pattern = re.compile(r'\(\=\s*\(moses-run\).*?\(FinalResult \$newR\)\)\)', re.DOTALL)
    if not pattern.search(content):
        print("ERROR: Could not find moses-run with regex.")
        sys.exit(1)

    new_block = helpers_code + "\n" + seeds_code + "\n\n" + NEW_MOSES_RUN
    content = pattern.sub(new_block, content)
    
    with open(FPATH, 'w') as f:
        f.write(content)

def parse_score(log_content):
    matches = re.findall(r'\(New best score:\s+([-\d\.]+)\)', log_content)
    if matches:
        return float(matches[-1])
    return None

def run_condition(name, out_dir, init_policy, seed_count):
    os.makedirs(out_dir, exist_ok=True)
    
    # Save a copy of the generated program for inspection
    shutil.copy(FPATH, os.path.join(out_dir, "moses.metta"))
    
    for seed in range(seed_count):
        print(f"[{name}] Running seed {seed}/{seed_count-1}...")
        
        start_time = time.time()
        cmd = ["bash", "-c", f"/home/nonplds/projects/metta-projects/metta-moses/run_petta.sh moses.metta -s --problem=parity3 --seed={seed} --initPolicy={init_policy} --maxGen=50 --nDeme=1"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        wall_time = time.time() - start_time
        
        with open(f"{out_dir}/seed_{seed}.log", "w") as f:
            f.write(result.stdout)
            if result.stderr:
                f.write("\nSTDERR:\n")
                f.write(result.stderr)
        
        final_score = parse_score(result.stdout)
        exact_solve = final_score == 0.0 if final_score is not None else False
        
        summary = {
            "seed": seed,
            "condition": name,
            "final_best_score": final_score,
            "exact_solve": exact_solve,
            "wall_seconds": wall_time,
            "error": result.returncode != 0
        }
        
        with open(f"{out_dir}/seed_{seed}.json", "w") as f:
            json.dump(summary, f, indent=2)

def save_config(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    try:
        git_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except:
        git_hash = "unknown"
    
    config = {
        "git_hash": git_hash,
        "maxGen": 50,
        "nDeme": 1,
        "optAlgo": "hc",
        "fsAlgo": "None",
        "complexityRatio": 3.5,
        "nEval": 10000,
        "capCoef": 50,
        "discProbe": False
    }
    with open(os.path.join(out_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["smoke", "screen", "confirm"], required=True)
    args = parser.parse_args()
    
    base_dir = "sandbox_bootstrap_decisive"
    save_config(base_dir)
    
    seed_count = 1
    run_P = True
    run_N = True
    
    if args.phase == "smoke":
        seed_count = 1
    elif args.phase == "screen":
        seed_count = 10
    elif args.phase == "confirm":
        seed_count = 30
        run_P = False # Confirmation only runs N
    
    try:
        if run_P:
            apply_condition(SEEDS_P, HELPERS)
            run_condition("P-R", os.path.join(base_dir, f"p_roulette_n{seed_count}"), "roulette", seed_count)
            run_condition("P-B", os.path.join(base_dir, f"p_bootstrap_n{seed_count}"), "bootstrap", seed_count)
            
        if run_N:
            apply_condition(SEEDS_N, HELPERS)
            run_condition("N-R", os.path.join(base_dir, f"n_roulette_n{seed_count}"), "roulette", seed_count)
            run_condition("N-B", os.path.join(base_dir, f"n_bootstrap_n{seed_count}"), "bootstrap", seed_count)
            
    finally:
        subprocess.run(["git", "checkout", FPATH], capture_output=True)
        print("Done! Source restored.")

if __name__ == "__main__":
    main()
