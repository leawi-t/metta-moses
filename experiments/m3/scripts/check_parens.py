import os

path = '/home/nonplds/projects/metta-projects/metta-moses/moses/demo-problems.metta'
with open(path, 'r') as f:
    content = f.read()

start = content.find("(= (getSeedTrees $pool)")
if start != -1:
    end = content.find("\n(= (scoreSeed", start)
    if end != -1:
        block = content[start:end]
        opens = block.count('(')
        closes = block.count(')')
        print(f"Opens: {opens}, Closes: {closes}")
    else:
        print("End not found.")
else:
    print("Start not found.")
