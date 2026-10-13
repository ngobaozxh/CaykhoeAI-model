from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from fontTools.subset import Options, Subsetter, parse_unicodes
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / "tmp_fonts"
OUT = ROOT / "fonts"
SRC = OUT / "src"

UNICODE_RANGES = (
    "U+0000-00FF,"
    "U+0102-0103,"
    "U+0110-0111,"
    "U+0128-0129,"
    "U+0168-0169,"
    "U+01A0-01A1,"
    "U+01AF-01B0,"
    "U+02C6-02C7,"
    "U+02D8-02DD,"
    "U+0300-0304,"
    "U+0306-0309,"
    "U+031B,"
    "U+0323,"
    "U+0329,"
    "U+1E00-1EFF,"
    "U+1EA0-1EF9,"
    "U+2000-206F,"
    "U+2010-2015,"
    "U+2018-201D,"
    "U+2020-2026,"
    "U+2030,"
    "U+2039-203A,"
    "U+20AB,U+20AC,"
    "U+2122,"
    "U+2190-2193,"
    "U+2212,U+2260"
)

GOOGLE_RANGES = {
    "vietnamese": "U+0102-0103,U+0110-0111,U+0128-0129,U+0168-0169,U+01A0-01A1,U+01AF-01B0,U+0300-0301,U+0303-0304,U+0308-0309,U+0323,U+0329,U+1EA0-1EF9,U+20AB",
    "latin-ext": "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF",
}

SOURCES = [
    ("fraunces_it.css", "Fraunces", "fraunces", {("normal", "300 600"), ("italic", "300 600")}),
    ("literata.css", "Literata", "literata", {("normal", "300 700")}),
    ("bvp.css", "Be Vietnam Pro", "be-vietnam-pro",
     {("normal", "300"), ("normal", "400"), ("normal", "500"), ("normal", "600")}),
]

BLOCK_RE = re.compile(
    r"/\*\s*(?P<label>[a-z-]+)\s*\*/\s*"
    r"@font-face\s*\{(?P<body>[^}]*)\}",
    re.S,
)

def parse_blocks(css_path: Path):
    css = css_path.read_text(encoding="utf-8")
    out = []
    for m in BLOCK_RE.finditer(css):
        body = m.group("body")
        style = re.search(r"font-style:\s*([a-z]+)", body)
        weight = re.search(r"font-weight:\s*([\d ]+)", body)
        url = re.search(r"url\((https://[^)]+\.woff2)\)", body)
        if not (style and weight and url):
            continue
        out.append({
            "label": m.group("label"),
            "style": style.group(1).strip(),
            "weight": weight.group(1).strip(),
            "url": url.group(1),
        })
    return out

def subset(src: Path, dst: Path) -> tuple[int, int]:
    opts = Options()
    opts.flavor = "woff2"
    opts.desubroutinize = True
    opts.layout_features = ["kern", "liga", "calt", "ccmp", "locl", "mark", "mkmk", "rlig"]
    opts.layout_closure = True
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    opts.recalc_bounds = True
    opts.drop_tables += ["DSIG"]

    font = TTFont(str(src), lazy=False)
    subsetter = Subsetter(options=opts)
    subsetter.populate(unicodes=parse_unicodes(UNICODE_RANGES))
    subsetter.subset(font)
    font.flavor = "woff2"
    font.save(str(dst))
    font.close()
    return src.stat().st_size, dst.stat().st_size

def main() -> int:
    OUT.mkdir(exist_ok=True)
    SRC.mkdir(exist_ok=True)

    for p in list(OUT.glob("*.woff2")):
        if p.is_file():
            p.unlink()

    rules: list[str] = []
    total_raw = total_sub = 0
    manifest: list[str] = []
    problem = False

    for css_name, family, slug, wanted in SOURCES:
        css_path = TMP / css_name
        if not css_path.exists():
            print(f"SKIP {family}: missing {css_path}", file=sys.stderr)
            problem = True
            continue
        kept = 0
        for b in parse_blocks(css_path):
            if b["label"] not in ("vietnamese", "latin-ext"):
                continue
            if (b["style"], b["weight"]) not in wanted:
                continue
            tag = {"vietnamese": "vi", "latin-ext": "lext"}[b["label"]]
            stem = f"{slug}-{b['weight'].replace(' ', '_')}-{b['style']}-{tag}"
            raw = SRC / f"{stem}.woff2"
            if not raw.exists():
                r = requests.get(b["url"], timeout=30)
                r.raise_for_status()
                raw.write_bytes(r.content)
            final = OUT / f"{stem}.woff2"
            a, c = subset(raw, final)

            t = TTFont(str(final))
            cmap = t.getBestCmap() or {}
            n = len(cmap)
            t.close()
            if n < 30:
                print(f"FAIL {family} {b['style']} {b['weight']} {tag}: only {n} glyphs",
                      file=sys.stderr)
                problem = True
                continue

            total_raw += a
            total_sub += c
            kept += 1
            rules.append(
                f"@font-face{{font-family:'{family}';font-style:{b['style']};"
                f"font-weight:{b['weight']};font-display:swap;"
                f"src:url(fonts/{final.name}) format('woff2');"
                f"unicode-range:{GOOGLE_RANGES[b['label']]}}}"
            )
            manifest.append(f"{final.name}\t{a}\t{c}\t{n}")
            print(f"{family:15} {b['style']:7} {b['weight']:8} {tag:5} "
                  f"{a:>7} -> {c:>6}  {n:>4} glyphs")
        if kept == 0:
            print(f"WARN {family}: no matching blocks", file=sys.stderr)
            problem = True

    (OUT / "fonts.css").write_text("\n".join(rules) + "\n", encoding="utf-8")
    (SRC / "SIZES.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(f"\nfiles: {len(rules)}   raw {total_raw} -> subset {total_sub}")
    return 1 if problem else 0

if __name__ == "__main__":
    raise SystemExit(main())
