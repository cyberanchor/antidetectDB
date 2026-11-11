#!/usr/bin/env python3
"""Write the product tables of README.md from data/products/, then align the | of every Markdown table.

Each table sits under its heading; the text between the heading and the table is kept, the table is rewritten:

  ## Antidetect browsers               closed-source browsers (kind browser)
  ## Open-source antidetect browsers   browsers with open_source: true
  ## Cloud phones                      kind cloud-phone

  Status   ✅ tested by hand · 🤖 collected from the vendor's pages and automatic checks · ⏳ not reviewed yet ·
           ❌ gone (name struck out)
  Core     engine and major version of the newest core, and how many major versions it is behind the current
           stable Chrome / Firefox (data/upstream.yaml); a Firefox core on the current ESR shows "ESR"

Widths are measured as a monospace editor shows them: emoji and wide characters take two columns, combining
marks and variation selectors none.

usage: python3 tools/readme_tables.py [README] [--check]   (--check: exit 1 when the file is not up to date)
"""
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addata  # noqa: E402

STATUS = {"checked": "✅", "auto": "🤖", "pending": "⏳"}
ENGINE = {"chromium": "Chromium", "firefox": "Firefox", "webkit": "WebKit"}
ZERO_WIDTH = {"‍", "︎", "️"}


def width(text):
    return sum(0 if unicodedata.combining(ch) or ch in ZERO_WIDTH
               else 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def align(rows):
    cells = [[c.strip() for c in re.split(r"(?<!\\)\|", row.strip().strip("|"))] for row in rows]
    ncol = max(len(r) for r in cells)
    cells = [r + [""] * (ncol - len(r)) for r in cells]
    sep = [i for i, r in enumerate(cells) if all(re.fullmatch(r":?-+:?", c) for c in r if c)]
    widths = [max([width(r[j]) for i, r in enumerate(cells) if i not in sep] + [3]) for j in range(ncol)]
    out = []
    for i, r in enumerate(cells):
        if i in sep:
            out.append("|" + "|".join(("-" * (widths[j] + 1) + ":" if cells[i][j].endswith(":") else
                                       "-" * (widths[j] + 2)) for j in range(ncol)) + "|")
        else:
            out.append("| " + " | ".join(c + " " * (widths[j] - width(c)) for j, c in enumerate(r)) + " |")
    return out


def esc(text):
    return str(text).replace("|", "\\|")


def status(r):
    return "❌" if r.get("dead") else STATUS.get(r.get("status"), "⏳")


def name(r):
    link = f"[{esc(r['name'])}](data/products/{r['_id']}.yaml)"
    return f"~~{link}~~" if r.get("dead") else link


def site(r):
    url = r.get("website")
    if not url:
        return "—"
    host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0])
    return f"[{host}]({url})"


def repo(r):
    m = re.match(r"^https://github\.com/([^/]+/[^/#?]+)", r.get("repo") or "")
    return f"[{m.group(1)}]({r['repo']})" if m else "—"


def engine(r):
    return ", ".join(ENGINE.get(e, e) for e in r.get("engine") or []) or "—"


def core(r, up):
    out = []
    for c in r.get("cores") or []:
        lag = addata.lag(c, up)
        v = addata.major(c.get("version"))
        text = f"{ENGINE.get(c.get('engine'), c.get('engine'))} {v}"
        if addata.is_esr(c, up):
            text += " (ESR)"
        elif lag is not None:
            text += " (current)" if lag == 0 else f" (−{lag})"
        out.append(text)
    return ", ".join(out) or "—"


def stars(r):
    return f"{r['stars']:,}" if isinstance(r.get("stars"), int) else "—"


TABLES = [
    ("## Antidetect browsers",
     lambda r: "browser" in r.get("kind", []) and not r.get("open_source"),
     ["Status", "Browser", "Website", "Flag", "Engine", "Core", "Free plan"],
     lambda r, up: [status(r), name(r), site(r), r.get("flag") or "❓", engine(r), core(r, up),
                    esc(r.get("free") or "—")]),
    ("## Open-source antidetect browsers",
     lambda r: "browser" in r.get("kind", []) and r.get("open_source"),
     ["Status", "Browser", "Repository", "Engine", "Core", "License", "Stars", "Last push"],
     lambda r, up: [status(r), name(r), repo(r), engine(r), core(r, up), r.get("license") or "—", stars(r),
                    r.get("pushed") or "—"]),
    ("## Cloud phones",
     lambda r: "cloud-phone" in r.get("kind", []),
     ["Status", "Cloud phone", "Website", "Flag", "Android", "Browser too"],
     lambda r, up: [status(r), name(r), site(r), r.get("flag") or "❓", ", ".join(r.get("android") or []) or "—",
                    "✓" if "browser" in r.get("kind", []) else ""]),
]
RIGHT = {"Stars"}


def table(head, rows):
    out = ["| " + " | ".join(head) + " |",
           "|" + "|".join("---:" if h in RIGHT else "---" for h in head) + "|"]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return out


def render(text, recs, up):
    lines = text.split("\n")
    for heading, keep, head, row in TABLES:
        try:
            i = next(n for n, line in enumerate(lines) if line.strip() == heading)
        except StopIteration:
            raise SystemExit(f'README: heading "{heading}" not found') from None
        j = i + 1
        while j < len(lines) and not lines[j].strip().startswith("|") and not lines[j].startswith("## "):
            j += 1
        if j >= len(lines) or not lines[j].strip().startswith("|"):
            raise SystemExit(f'README: no table under "{heading}"')
        k = j
        while k < len(lines) and lines[k].strip().startswith("|"):
            k += 1
        rows = [row(r, up) for r in recs if keep(r)]
        lines[j:k] = table(head, rows)
    final, block = [], []
    for line in lines + [""]:
        if line.strip().startswith("|"):
            block.append(line)
            continue
        if block:
            final += align(block)
            block = []
        final.append(line)
    return "\n".join(final[:-1])


def main():
    args = [a for a in sys.argv[1:] if a != "--check"]
    path = args[0] if args else os.path.join(addata.ROOT, "README.md")
    text = open(path, encoding="utf-8").read()
    recs = addata.load_all()
    new = render(text, recs, addata.upstream())
    if "--check" in sys.argv:
        if new != text:
            raise SystemExit(f"{path}: the product tables are not up to date; run python3 tools/readme_tables.py")
        print(f"{path}: product tables up to date ({len(recs)} products)")
        return
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print(f"{path}: {len(recs)} products")


if __name__ == "__main__":
    main()
