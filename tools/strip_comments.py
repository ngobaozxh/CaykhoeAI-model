from __future__ import annotations

import ast
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP = ROOT / ".comment-strip-backup"
BACKUP.mkdir(exist_ok=True)

def backup(path: Path) -> None:
    rel = path.relative_to(ROOT)
    dest = BACKUP / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)

def strip_css_comments(text: str) -> str:

    out = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    out = re.sub(r"\n{3,}", "\n\n", out)
    return out

def strip_js(text: str) -> str:

    out = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    lines = []
    for line in out.split("\n"):
        if line.strip().startswith("//"):
            continue
        lines.append(line)
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out)

def strip_python(text: str) -> str:

    tree = ast.parse(text)
    doc_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                doc = body[0]
                start = doc.lineno - 1
                end = doc.end_lineno
                doc_lines.update(range(start, end))

    kept = []
    for i, line in enumerate(text.split("\n")):
        if i in doc_lines:
            continue
        kept.append(_trim_hash(line))
    out = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", out)

def _trim_hash(line: str) -> str:
    quote = None
    escaped = False
    for i, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == "#":
            trimmed = line[:i].rstrip()
            return trimmed if trimmed else ""
    return line

def strip_html(text: str) -> str:
    out = re.sub(r"<!--.*?-->", "", text, flags=re.S)

    out = re.sub(r"<style>(.*?)</style>",
                 lambda m: "<style>" + re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S) + "</style>",
                 out, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", out)

def verify(rel: str, text: str) -> None:
    if rel.endswith(".py"):
        ast.parse(text)
    elif rel.endswith(".js") or rel.endswith(".cjs"):

        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(text)
            tmp = fh.name
        try:
            r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
            if r.returncode != 0:
                raise SyntaxError(r.stderr.strip()[:500])
        finally:
            Path(tmp).unlink()
    elif rel.endswith(".html"):

        for tag in ("style", "script", "div", "form", "aside", "svg"):
            opens = len(re.findall(rf"<{tag}[\s>]", text))
            closes = len(re.findall(rf"</{tag}>", text))
            if tag in ("svg",) and opens != closes:
                raise SyntaxError(f"<{tag}> unbalanced: {opens} open / {closes} close")
        if text.count("<style>") != text.count("</style>"):
            raise SyntaxError("<style> unbalanced")

def main() -> int:
    targets = {
        "index.html": strip_html,
        "app.js": strip_js,
        "sw.js": strip_js,
    }
    for p in sorted((ROOT / "tools").glob("*.py")):
        targets[str(p.relative_to(ROOT)).replace("\\", "/")] = strip_python
    for p in sorted((ROOT / "tools").glob("*.cjs")):
        targets[str(p.relative_to(ROOT)).replace("\\", "/")] = strip_js

    changed = []
    for rel, fn in targets.items():
        path = ROOT / rel
        if not path.is_file():
            print("skip (missing):", rel)
            continue
        original = path.read_text(encoding="utf-8")
        if fn is strip_python:
            original_clean = original
        else:
            original_clean = original
        stripped = fn(original_clean)
        if stripped == original:
            print("unchanged:", rel)
            continue

        try:
            verify(rel, stripped)
        except Exception as exc:
            print(f"REFUSED {rel}: {exc}")
            continue
        backup(path)
        path.write_text(stripped, encoding="utf-8")
        changed.append((rel, len(original) - len(stripped)))

    print("\nstripped comments from", len(changed), "files:")
    for rel, saved in changed:
        print(f"  {rel}  -{saved} chars")
    print("\nbackups in", BACKUP.relative_to(ROOT))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
