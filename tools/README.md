# Tools

Scripts that check the products and keep the files in sync. Python 3.9+ with PyYAML (`dnf install python3-pyyaml`);
the collector also needs `dig`. The data is `data/products/<id>.yaml`, one file per product (fields:
`data/README.md`); every script reads and writes it through `addata.py`, so the files keep one format.
`ADB_DATA_DIR=/other/folder` points the scripts at a copy of the data, `ADB_UA` sets the User-Agent of the checks.

| Script | What it does |
|---|---|
| `addata.py` | Shared module: load / save the records in the canonical YAML format (quotes anything a YAML 1.2 parser would not read as text, refuses unknown fields, wrong types and unknown values), the core lag |
| `upstream.py [--check]` | Writes `data/upstream.yaml`: the Chrome stable release that serves most users (Google's VersionHistory API) and the current Firefox and Firefox ESR (Mozilla's product-details) |
| `collect.py --all \| ID... [--only STEPS] [--dry-run]` | Automatic checks; steps `web` (status code of the website), `hosting` (address, country, network: `dig`, ip-api.com), `rdap` (domain registration and expiry), `wayback` (first capture), `github` (stars, last push, licence, latest release; `GITHUB_TOKEN` raises the rate limit). A failed check keeps the old value |
| `readme_tables.py [--check]` | Writes the three product tables of `README.md` from the records and aligns every table |
| `test_data.py [--no-site]` | Checks every file (fields, types, id, canonical format, successors), `upstream.yaml`, the README tables and the built site (`site/public/`: `products.json` equal to the records, one page per product, the table rows). Run it after every change and after `site/build.sh` |

Refresh, in this order:

```bash
python3 tools/upstream.py
python3 tools/collect.py --all
python3 tools/readme_tables.py
HUGO=/path/to/hugo site/build.sh
python3 tools/test_data.py
```

What the checks do not do: they create no account and download no software. Facts that need a person (the company,
the core version from a changelog, plans and prices, tests by hand) are edited in the YAML files, with the page
they come from in `sources`. Do not work around a bot check with another User-Agent; read the page from the Wayback
Machine instead.
