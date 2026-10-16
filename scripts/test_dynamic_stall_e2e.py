import subprocess
import re
import sys

REPO_DIR = "/home/nonplds/projects/metta-projects/metta-moses-representation"
PETTA_RUNNER = "/home/nonplds/projects/metta-projects/PeTTa/run.sh"

cmd = [
    "bash",
    PETTA_RUNNER,
    "moses.metta",
    "-s",
    "--problem=parity4",
    "--maxGen=6",
    "--stallRelaxationMode=dynamic",
    "--baseComplexityRatio=14.0",
    "--relaxedComplexityRatio=100.0",
    "--stallThresholdK=2",
    "--relaxWindowMinM=2",
    "--relaxGraceG=1",
    "--relaxCooldownC=2",
    "--seed=1"
]

print("Running command:", " ".join(cmd))
proc = subprocess.run(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
out = proc.stdout
err = proc.stderr

print("\n--- MATCHING TELEMETRY LINES ---")
for line in out.splitlines():
    if any(k in line for k in ["Step2-GenStats", "RatioSwitchedTo", "Step2-Summary", "Step2-BestRaw", "FinalResult"]):
        print(line)

if proc.returncode != 0:
    print(f"\nCommand failed with code {proc.returncode}!")
    print("\n--- STDERR ---")
    print(err)
    sys.exit(1)

# Check for expected markers
has_switch = "RatioSwitchedTo: 100" in out
has_effective = "EffectiveRatio: 100" in out
has_summary = "Step2-Summary" in out
has_final = "FinalResult" in out

print("\n--- VERIFICATION CHECKS ---")
print(f"RatioSwitchedTo: 100 present? {'✅ YES' if has_switch else '❌ NO'}")
print(f"EffectiveRatio: 100 present? {'✅ YES' if has_effective else '❌ NO'}")
print(f"Step2-Summary present? {'✅ YES' if has_summary else '❌ NO'}")
print(f"FinalResult present? {'✅ YES' if has_final else '❌ NO'}")

if has_switch and has_effective and has_summary and has_final:
    print("\n🎉 ALL E2E VERIFICATION CHECKS PASSED!")
else:
    print("\n❌ SOME CHECKS FAILED!")
    sys.exit(1)
