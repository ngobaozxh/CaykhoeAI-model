"""Assemble a deployment-ready site into _site/.

GitHub Pages serves a repository from a subpath such as
https://<user>.github.io/<repo>/, so the deployable tree must contain only the
files the application actually requests at runtime, and every one of them must
be present and complete. Shipping the whole working tree is what breaks a
deploy: the outputs/ directory alone is hundreds of megabytes of test
artifacts, which pushes the published site past the Pages size budget and
leaves a partial deployment behind.

What this does:
  1. Copies the runtime file set into _site/ (never the test artifacts).
  2. Verifies each file exists, is non-empty, and matches an expected floor.
  3. Parses the references out of index.html, app.js and sw.js and confirms
     every local one resolves inside _site/.
  4. Writes .nojekyll so Pages serves the tree verbatim.
  5. Refuses to finish if anything is missing, naming each offender.

Run:  python tools/build_deploy.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "_site"

# Directories and files that make up the running site. Anything not listed here
# is deliberately left out of the deployment.
RUNTIME_DIRS = ["vendor", "img", "model/quant"]
RUNTIME_FILES = [
    "index.html",
    "app.js",
    "sw.js",
    "manifest.webmanifest",
    "dieu_tri.json",
]

# Minimum plausible size per file. A truncated or placeholder file fails here
# rather than in the browser.
MIN_BYTES = {
    "index.html": 15_000,
    "app.js": 15_000,
    "sw.js": 1_000,
    "manifest.webmanifest": 200,
    "dieu_tri.json": 1_000,
    "model/quant/model.json": 50_000,
    "model/quant/group1-shard1of1.bin": 1_000_000,
    "vendor/tf.min.js": 500_000,
    "vendor/tf-backend-wasm.min.js": 50_000,
    "vendor/tfjs-backend-wasm.wasm": 100_000,
    "vendor/tfjs-backend-wasm-simd.wasm": 100_000,
    "vendor/tfjs-backend-wasm-threaded-simd.wasm": 100_000,
    "vendor/html2pdf.bundle.min.js": 300_000,
    "img/icon-64.png": 500,
    "img/icon-192.png": 500,
    "img/icon-512.png": 500,
}
# Every woff2 subset is small; anything under this is a failed subset.
MIN_FONT_BYTES = 500


def active_variant() -> str:
    """The model variant app.js actually loads at runtime.

    app.js picks between two folders with a constant. Only the active one is
    deployed, so the verifier must not demand the rollback copy.
    """
    src = (ROOT / "app.js").read_text(encoding="utf-8")
    m = re.search(r"MODEL_VARIANT\s*=\s*['\"]([a-z0-9_]+)['\"]", src)
    return m.group(1) if m else "quant"


def model_shards(variant: str) -> list[str]:
    """Shard paths declared by the active model.json, as project-relative paths."""
    manifest = ROOT / "model" / variant / "model.json"
    if not manifest.is_file():
        return []
    data = json.loads(manifest.read_text(encoding="utf-8"))
    shards: list[str] = []
    for group in data.get("weightsManifest", []):
        for path in group.get("paths", []):
            shards.append(f"model/{variant}/{path}")
    return shards


def expected_files() -> list[str]:
    """The exact runtime file set, fonts discovered from disk."""
    files = list(RUNTIME_FILES)
    for name in RUNTIME_DIRS:
        d = ROOT / name
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file():
                files.append(str(p.relative_to(ROOT)).replace("\\", "/"))
    for p in sorted((ROOT / "fonts").glob("*.woff2")):
        files.append(f"fonts/{p.name}")
    # Every shard the active model.json declares must ship with it.
    files.extend(model_shards(active_variant()))
    return sorted(set(files))


def local_refs(text: str, source: str) -> set[str]:
    """Local paths a source file references, normalised to project-relative."""
    found: set[str] = set()
    # src="..." / href="..." / url(...) in HTML and CSS
    for m in re.finditer(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', text):
        found.add(m.group(1))
    for m in re.finditer(r"url\(\s*['\"]?([^'\")]+)", text):
        found.add(m.group(1))
    # string literals that look like a path with a known extension
    for m in re.finditer(
        r"""['"]([A-Za-z0-9_./\-]+\.(?:json|js|wasm|bin|png|webmanifest|woff2|css|html))['"]""",
        text,
    ):
        found.add(m.group(1))

    out: set[str] = set()
    for ref in found:
        ref = ref.strip()
        if not ref or ref.startswith(("data:", "http:", "https:", "//", "#", "blob:")):
            continue
        if ref.startswith("./"):
            ref = ref[2:]
        if ref in ("", ".", "/"):
            continue
        # Only keep refs that name a real project file or a runtime directory.
        if (ROOT / ref).exists() or "/" in ref:
            out.add(ref.lstrip("/"))
    return out


def clean_dir(path: Path, keep: set[str], problems: list[str]) -> None:
    """Remove anything in path that is not part of the runtime file set.

    shutil.rmtree is unavailable in this sandbox and deletion can fail outright,
    so each file is attempted individually and a failure is reported rather than
    raised. A stale file that cannot be removed is surfaced as a problem, since
    it would otherwise be published.
    """
    if not path.exists():
        return
    for p in sorted(path.rglob("*"), reverse=True):
        if not (p.is_file() or p.is_symlink()):
            continue
        rel = str(p.relative_to(path)).replace("\\", "/")
        if rel in keep or rel == ".nojekyll":
            continue
        try:
            p.unlink()
        except OSError as exc:
            problems.append(f"stale file could not be removed: {rel} ({exc})")
    for p in sorted((d for d in path.rglob("*") if d.is_dir()), reverse=True):
        try:
            p.rmdir()
        except OSError:
            pass


def main() -> int:
    problems: list[str] = []

    # --- 1. assemble --------------------------------------------------------
    wanted = expected_files()
    keep = set(wanted)
    SITE.mkdir(parents=True, exist_ok=True)
    clean_dir(SITE, keep, problems)

    for rel in wanted:
        src = ROOT / rel
        if not src.is_file():
            problems.append(f"missing at source: {rel}")
            continue
        dst = SITE / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # --- 2. per-file size floor --------------------------------------------
    for rel in wanted:
        dst = SITE / rel
        if not dst.is_file():
            continue
        size = dst.stat().st_size
        if rel.startswith("fonts/"):
            floor = MIN_FONT_BYTES
        elif rel.startswith("model/") and rel.endswith(".bin"):
            floor = 1_000_000
        else:
            floor = MIN_BYTES.get(rel, 1)
        if size < floor:
            problems.append(f"too small ({size} < {floor}): {rel}")

    # --- 2b. nothing unexpected may be published ---------------------------
    allowed = set(wanted) | {".nojekyll"}
    for p in sorted(SITE.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(SITE)).replace("\\", "/")
        if rel not in allowed:
            problems.append(f"unexpected file would be published: {rel}")

    # --- 3. referenced paths must resolve inside _site ---------------------
    variant = active_variant()
    inactive_model = f"model/{'model.json' if variant == 'quant' else 'quant/'}"
    for source in ("index.html", "app.js", "sw.js", "fonts/fonts.css"):
        p = ROOT / source
        if not p.is_file():
            continue
        for ref in sorted(local_refs(p.read_text(encoding="utf-8"), source)):
            # The model folder holds the rollback copy of the other variant.
            # app.js selects between them with a constant, so only the active
            # one is deployed and the dead branch is not a defect.
            if ref.startswith("model/") and not ref.startswith(f"model/{variant}/"):
                continue
            # A ref is fine when the file exists in _site, or when it is a
            # directory served as index, or a runtime path handled elsewhere.
            target = SITE / ref
            if target.is_file() or (target / "index.html").is_file():
                continue
            # sw.js precaches './' which maps to index.html
            if ref in ("./", "."):
                continue
            problems.append(f"{source} references '{ref}' which is not in _site")

    # --- 4. service worker must precache only files we ship ----------------
    sw = (ROOT / "sw.js").read_text(encoding="utf-8")
    m = re.search(r"const FILES\s*=\s*\[(.*?)\];", sw, re.S)
    if not m:
        problems.append("sw.js: could not locate the FILES precache list")
    else:
        listed = re.findall(r"'([^']+)'", m.group(1))
        for rel in listed:
            if rel in ("./", "."):
                continue
            if not (SITE / rel).is_file():
                problems.append(f"sw.js precaches '{rel}' which is not in _site")

    # --- 5. .nojekyll -------------------------------------------------------
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    # --- report -------------------------------------------------------------
    total = sum(p.stat().st_size for p in SITE.rglob("*") if p.is_file())
    count = sum(1 for p in SITE.rglob("*") if p.is_file())
    model = SITE / "model/quant/group1-shard1of1.bin"
    report = {
        "ok": not problems,
        "files": count,
        "total_bytes": total,
        "model_bytes": model.stat().st_size if model.is_file() else 0,
        "fonts": len(list((SITE / "fonts").glob("*.woff2"))),
        "problems": problems,
    }
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs" / "deploy-validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"_site: {count} files, {total:,} bytes "
          f"({total / 1024 / 1024:.1f} MiB), model {report['model_bytes']:,} bytes, "
          f"{report['fonts']} fonts")
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for p in problems:
            print("  -", p)
        return 1
    print("all runtime references resolve; .nojekyll written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
