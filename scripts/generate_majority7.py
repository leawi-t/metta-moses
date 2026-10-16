import csv
import itertools
from pathlib import Path

def generate_majority7_csv(filepath: Path):
    rows = []
    # 7 variables: X1, X2, X3, X4, X5, X6, X7
    # Out is 1 if >= 4 True, else 0
    header = ["X1", "X2", "X3", "X4", "X5", "X6", "X7", "Out"]
    for combo in itertools.product([0, 1], repeat=7):
        out = 1 if sum(combo) >= 4 else 0
        rows.append(list(combo) + [out])
    
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"Generated {len(rows)} rows to {filepath}")

def generate_metta_majority7():
    # Column-major format for demo-problems.metta
    # 7 input columns + 1 output column
    all_rows = list(itertools.product([False, True], repeat=7))
    cols = []
    for c in range(7):
        cols.append([r[c] for r in all_rows])
    out_col = [sum(r) >= 4 for r in all_rows]
    cols.append(out_col)
    
    metta_code = "(= (majority7) (mkITable\n"
    metta_code += "                ("
    for i, col in enumerate(cols):
        col_str = " ".join("True" if v else "False" for v in col)
        if i == 0:
            metta_code += f"({col_str})\n"
        else:
            metta_code += f"                 ({col_str})" + ("\n" if i < len(cols) - 1 else "))\n")
    metta_code += "                (X1 X2 X3 X4 X5 X6 X7 Out)))\n"
    return metta_code

if __name__ == "__main__":
    csv_path = Path("/home/nonplds/projects/metta-projects/metta-moses-representation/majority7.csv")
    generate_majority7_csv(csv_path)
    
    csv_py_path = Path("/home/nonplds/projects/metta-projects/pyMOSES/majority7.csv")
    generate_majority7_csv(csv_py_path)
    
    metta_def = generate_metta_majority7()
    with open("/home/nonplds/projects/metta-projects/metta-moses-representation/majority7_def.metta", "w") as f:
        f.write(metta_def)
    print("Generated majority7_def.metta")
