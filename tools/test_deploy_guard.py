"""Prove the deploy assembler refuses to publish an incomplete site.

Runs the REAL tools/build_deploy.py against two throwaway sandbox roots, so the
guard is tested without touching the working tree:

  _deploytest_missing/  model weights deliberately absent -> must fail
  _deploytest_full/     complete runtime set              -> must succeed

Each sandbox is built fresh; nothing is deleted, because this environment
blocks bulk deletion and the sandboxes are gitignored anyway.
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(".").resolve()
PY_EXE = sys.executable

SMALL = ["index.html", "app.js", "sw.js", "manifest.webmanifest", "dieu_tri.json"]


def build_sandbox(dest: Path, with_weights: bool) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "tools").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "tools/build_deploy.py", dest / "tools/build_deploy.py")
    for rel in SMALL:
        shutil.copy2(ROOT / rel, dest / rel)
    for d in ["vendor", "img"]:
        shutil.copytree(ROOT / d, dest / d, dirs_exist_ok=True)
    (dest / "fonts").mkdir(exist_ok=True)
    for f in (ROOT / "fonts").glob("*.woff2"):
        shutil.copy2(f, dest / "fonts" / f.name)
    shutil.copy2(ROOT / "fonts/fonts.css", dest / "fonts/fonts.css")
    (dest / "model/quant").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "model/quant/model.json", dest / "model/quant/model.json")
    if with_weights:
        shutil.copy2(ROOT / "model/quant/group1-shard1of1.bin",
                     dest / "model/quant/group1-shard1of1.bin")


def run(dest: Path):
    return subprocess.run([PY_EXE, "tools/build_deploy.py"], cwd=dest,
                          capture_output=True, text=True)


missing = ROOT / "_deploytest_missing"
full = ROOT / "_deploytest_full"
build_sandbox(missing, with_weights=False)
build_sandbox(full, with_weights=True)

print("=== A. thieu trong so model (phai that bai) ===")
a = run(missing)
print("exit:", a.returncode)
print((a.stdout or a.stderr).strip()[-700:])
ok_fail = a.returncode == 1 and "group1-shard1of1.bin" in a.stdout

print("\n=== B. du tep (phai thanh cong) ===")
b = run(full)
print("exit:", b.returncode)
print((b.stdout or b.stderr).strip()[-400:])
ok_pass = b.returncode == 0

print("\n=== KET QUA ===")
print("A. bat duoc thieu weights :", ok_fail)
print("B. qua khi du tep         :", ok_pass)
print("CA HAI DAT                :", ok_fail and ok_pass)
sys.exit(0 if (ok_fail and ok_pass) else 1)
