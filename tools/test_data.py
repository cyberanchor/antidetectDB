#!/usr/bin/env python3
"""Check the product data and what is built from it. Exit code 1 and a list of problems when something is wrong.

  files     every data/products/*.yaml: fields, types and values (addata.check), a valid id as file name, the
            canonical format (the file reads back to exactly what addata would write), successors that exist
  upstream  data/upstream.yaml has the Chrome and Firefox versions
  README    the product tables match the records (tools/readme_tables.py --check)
  site      site/public/: products.json equals the records, products.csv has one row per product, one page per
            product and no other, one table row per product on the home page (skipped with --no-site)

usage: python3 tools/test_data.py [--no-site]
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addata  # noqa: E402
import readme_tables  # noqa: E402

PUBLIC = os.path.join(addata.ROOT, "site", "public")


def check_files(problems):
    recs = addata.load_all()
    ids = {r["_id"] for r in recs}
    for r in recs:
        f = f"data/products/{r['_id']}.yaml"
        found = addata.check(r)
        problems += [f"{f}: {p}" for p in found]
        if not addata.ID.match(r["_id"]):
            problems.append(f"{f}: the file name must be lower-case letters, digits and single dashes")
        if not found:
            with open(addata.path(r["_id"]), encoding="utf-8") as fh:
                if fh.read() != addata.dumps(r):
                    problems.append(f"{f}: not in the canonical format; load and save it with addata")
        succ = r.get("successor")
        if succ and succ not in ids:
            problems.append(f"{f}: successor {succ!r} has no record")
    names = {}
    for r in recs:
        key = str(r.get("name", "")).lower()
        if key in names:
            problems.append(f"data/products/{r['_id']}.yaml: same name as {names[key]}")
        names[key] = r["_id"]
    return recs


def check_upstream(problems):
    try:
        up = addata.upstream()
    except OSError as e:
        problems.append(f"data/upstream.yaml: {e} (python3 tools/upstream.py)")
        return {}
    for k in ("chrome", "firefox"):
        if addata.major((up.get(k) or {}).get("version")) is None:
            problems.append(f"data/upstream.yaml: no {k} version (python3 tools/upstream.py)")
    return up


def check_readme(recs, up, problems):
    path = os.path.join(addata.ROOT, "README.md")
    text = open(path, encoding="utf-8").read()
    if readme_tables.render(text, recs, up) != text:
        problems.append("README.md: the product tables are not up to date (python3 tools/readme_tables.py)")


def check_site(recs, problems):
    if not os.path.isdir(PUBLIC):
        problems.append("site/public/ is missing (site/build.sh)")
        return
    want = [dict({"id": r["_id"]}, **{k: v for k, v in r.items() if k != "_id"}) for r in recs]
    with open(os.path.join(PUBLIC, "products.json"), encoding="utf-8") as f:
        have = json.load(f)
    if sorted(have, key=lambda r: r.get("id", "")) != sorted(want, key=lambda r: r["id"]):
        problems.append("site/public/products.json differs from data/products/ (rebuild with site/build.sh)")
    with open(os.path.join(PUBLIC, "products.csv"), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if sorted(r["id"] for r in rows) != sorted(r["_id"] for r in recs):
        problems.append("site/public/products.csv: the rows do not match the records")
    ids = {r["_id"] for r in recs}
    pages = set(os.listdir(os.path.join(PUBLIC, "products"))) if os.path.isdir(os.path.join(PUBLIC, "products")) else set()
    for s in sorted(ids - pages):
        problems.append(f"site/public/products/{s}/ is missing")
    for s in sorted(pages - ids):
        problems.append(f"site/public/products/{s}/ has no record (rebuild with site/build.sh)")
    with open(os.path.join(PUBLIC, "index.html"), encoding="utf-8") as f:
        links = re.findall(r'<a href="?products/([^/"]+)/"?>', f.read())
    if sorted(links) != sorted(ids):
        problems.append(f"site/public/index.html: {len(links)} table rows for {len(recs)} products")


def main():
    problems = []
    recs = check_files(problems)
    up = check_upstream(problems)
    if up:
        check_readme(recs, up, problems)
    if "--no-site" not in sys.argv:
        check_site(recs, problems)
    for p in problems:
        print(p)
    counts = {}
    for r in recs:
        s = "dead" if r.get("dead") else r.get("status", "?")
        counts[s] = counts.get(s, 0) + 1
    summary = ", ".join(f"{n} {s}" for s, n in sorted(counts.items(), key=lambda x: -x[1]))
    print(f"{len(recs)} products ({summary}): {'%d problems' % len(problems) if problems else 'all checks passed'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
