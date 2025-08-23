import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = "MaskPruner.py"
OUTNAME = "MaskPruner.exe"

# gather files in project root matching extensions
exts = {".png", ".ico", ".wav"}
files = [p for p in ROOT.iterdir() if p.suffix.lower() in exts and p.is_file()]

if not files:
    print("No .png/.ico/.wav files found in project root.")

# build --add-data args (Windows format src;dest). Use absolute paths to be safe.
add_args = []
for p in files:
    src = str(p)
    dst = "."  # place at bundle root
    # Quote each side and join with semicolon for PyInstaller on Windows
    # Use shlex.quote for safety; subprocess will handle args list anyway
    add_args.extend(["--add-data", f"{src};{dst}"])

cmd = ["pyinstaller", "--onefile", "--windowed", "--icon", "./app_icon.ico", "--name", OUTNAME] + add_args + [ENTRY]

# Print command for review
print("Running command:")
print(" ".join(shlex.quote(c) for c in cmd))

# Run the command
proc = subprocess.run(cmd)
if proc.returncode == 0:
    print("Build finished. Check the dist/ directory.")
else:
    print(f"PyInstaller exited with code {proc.returncode}.")
