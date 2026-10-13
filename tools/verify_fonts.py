from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"

VIETNAMESE = {
    "i_hook": 0x1EC9,
    "e_dot": 0x1EC7,
    "o_horn": 0x01A1,
    "a_dot": 0x1EA1,
    "a_tilde": 0x1EAB,
    "o_grave": 0x1ED3,
    "o_dot": 0x1ECD,
    "u_grave": 0x1EEB,
    "a_circ_grave": 0x1EA7,
    "d_stroke": 0x0110,
    "u_dot": 0x1EE5,
    "a_breve": 0x0103,
    "u_horn": 0x01B0,
}

INLINE_MARK = "data:font/woff2;base64,"

def check(results, name, value, detail=None):
    entry = {"name": name, "passed": bool(value)}
    if detail is not None:
        entry["detail"] = detail
    results.append(entry)
    return bool(value)

def main() -> int:
    results = []
    OUT.mkdir(exist_ok=True)

    css = (ROOT / "fonts/fonts.css").read_text(encoding="utf-8")
    referenced = sorted(set(re.findall(r"url\(fonts/([^)]+\.woff2)\)", css)))
    faces = css.count("@font-face")
    check(results, "fonts.css declares at least one @font-face", faces > 0, f"{faces} rules")

    missing = [n for n in referenced if not (ROOT / "fonts" / n).is_file()]
    check(results, "every font referenced by the CSS exists on disk",
          not missing, f"missing: {missing}" if missing else f"{len(referenced)} files")

    empt = [n for n in referenced
            if (ROOT / "fonts" / n).is_file() and (ROOT / "fonts" / n).stat().st_size < 200]
    check(results, "no referenced font file is empty or truncated",
          not empt, f"too small: {empt}" if empt else "all non-trivial")

    vi_files = [n for n in referenced if n.endswith("-vi.woff2")]
    check(results, "a vietnamese slice exists for each declared family",
          len(vi_files) >= 3, f"{len(vi_files)} slices")

    gaps = {}
    for name in vi_files:
        font = TTFont(str(ROOT / "fonts" / name))
        cmap = font.getBestCmap() or {}
        missing_chars = [k for k, cp in VIETNAMESE.items() if cp not in cmap]
        font.close()
        if missing_chars:
            gaps[name] = missing_chars
    check(results, "every vietnamese slice covers the rendered diacritics",
          not gaps, f"gaps: {gaps}" if gaps else f"{len(vi_files)} slices complete")

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    remote = (html.count("fonts.googleapis")
              + html.count("fonts.gstatic")
              + len(re.findall(r"@import\s+url\(\s*['\"]?https?:", html)))
    check(results, "index.html makes no remote font request", remote == 0, f"{remote} found")

    inline_faces = html.count("@font-face")
    check(results, "index.html carries the @font-face rules inline",
          inline_faces >= faces, f"{inline_faces} inline vs {faces} in fonts.css")

    html_refs = set(re.findall(r"url\(fonts/([^)]+\.woff2)\)", html))
    assert html_refs == set(referenced), (
        "index.html and fonts.css disagree: "
        f"only-in-html={sorted(html_refs - set(referenced))} "
        f"only-in-css={sorted(set(referenced) - html_refs)}"
    )
    check(results, "index.html and fonts.css reference the same file set",
          True, f"{len(html_refs)} files")

    sw = (ROOT / "sw.js").read_text(encoding="utf-8")
    sw_missing = [n for n in referenced if f"fonts/{n}" not in sw]
    check(results, "service worker precaches every font",
          not sw_missing, f"missing: {sw_missing}" if sw_missing else f"{len(referenced)} listed")

    bundle = ROOT / "outputs/cay-khoe-ai-1file.html"
    if bundle.is_file():
        text = bundle.read_text(encoding="utf-8")
        inlined = text.count(INLINE_MARK)
        check(results, "single-file bundle inlines every font",
              inlined == len(referenced), f"{inlined} inline vs {len(referenced)} expected")
        check(results, "single-file bundle keeps no external font path",
              "fonts/" not in text and "fonts.gstatic" not in text
              and "fonts.googleapis" not in text, "clean")
        check(results, "single-file bundle drops the now-redundant preload tags",
              'rel="preload"' not in text, "none")
    else:
        check(results, "single-file bundle exists", False, str(bundle))

    passed = sum(1 for c in results if c["passed"])
    report = {
        "tests": results,
        "passed": passed,
        "total": len(results),
        "ok": passed == len(results),
        "fonts_referenced": len(referenced),
        "vietnamese_slices": len(vi_files),
        "total_font_bytes": sum((ROOT / "fonts" / n).stat().st_size for n in referenced),
    }
    (OUT / "font-validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for c in results:
        print(("PASS " if c["passed"] else "FAIL ") + c["name"]
              + (f"  [{c['detail']}]" if c.get("detail") else ""))
    print(f"\n{passed}/{len(results)} passed; "
          f"{report['total_font_bytes']} bytes across {len(referenced)} files")
    return 0 if report["ok"] else 1

if __name__ == "__main__":
    sys.exit(main())
