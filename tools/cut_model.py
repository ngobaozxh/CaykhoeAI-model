import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
m = json.loads((root / "model/model.json").read_text(encoding="utf-8"))
specs = {s["name"]: s for s in m["weightsManifest"][0]["weights"]}
print("Original classifier input:", specs["dense/kernel"]["shape"][0])
print("Truncated backbone channels:", specs["block_13_project_BN/gamma"]["shape"][0])
raise SystemExit("Truncation blocked: retrain a compatible head using the original dataset first.")
