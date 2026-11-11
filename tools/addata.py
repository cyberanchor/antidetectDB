#!/usr/bin/env python3
"""Product data of antidetectDB: data/products/<id>.yaml, one file per product.

Shared by the collector, the README writer and the tests. Fields: data/README.md.

    load_all()        -> every record, sorted by name; the id (file name) is in rec["_id"]
    load(pid)         -> one record
    save(pid, rec)    -> writes data/products/<id>.yaml in the canonical format
    dumps(rec)        -> the canonical YAML text of a record
    check(rec)        -> list of problems (unknown fields, wrong types, unknown values); empty when fine
    upstream()        -> data/upstream.yaml: current stable Chrome and Firefox versions
    lag(core, up)     -> how many major versions a core is behind the current stable release, or None
"""
import glob
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DIR = os.environ.get("ADB_DATA_DIR") or os.path.join(DATA, "products")
UPSTREAM = os.path.join(DATA, "upstream.yaml")
HEADER = "# antidetectDB product record; fields are described in data/README.md\n"

TEXT, BOOL, INT, LIST, MAP, MAPS = "text", "bool", "int", "list", "map", "maps"
# Field: (type, sub-fields of a map / of the maps in a list). Records are written in this order.
FIELDS = {
    "name": (TEXT, None),
    "kind": (LIST, None),
    "status": (TEXT, None),
    "dead": (BOOL, None),
    "successor": (TEXT, None),
    "website": (TEXT, None),
    "domains": (LIST, None),
    "legal_entity": (TEXT, None),
    "flag": (TEXT, None),
    "country": (TEXT, None),
    "alliance": (INT, None),
    "law": (TEXT, None),
    "engine": (LIST, None),
    "cores": (MAPS, {"name": TEXT, "engine": TEXT, "version": TEXT}),
    "platforms": (LIST, None),
    "android": (LIST, None),
    "open_source": (BOOL, None),
    "repo": (TEXT, None),
    "license": (TEXT, None),
    "stars": (INT, None),
    "pushed": (TEXT, None),
    "release": (MAP, {"version": TEXT, "date": TEXT}),
    "free": (TEXT, None),
    "trial": (TEXT, None),
    "price": (LIST, None),
    "payment": (LIST, None),
    "storage": (TEXT, None),
    "api": (BOOL, None),
    "tests": (MAP, {"date": TEXT, "version": TEXT, "creepjs": TEXT, "pixelscan": TEXT, "browserscan": TEXT,
                    "iphey": TEXT, "fingerprint_com": TEXT, "webrtc": TEXT, "note": TEXT}),
    "incidents": (MAPS, {"date": TEXT, "text": TEXT, "links": LIST}),
    "note": (TEXT, None),
    "links": (MAP, {"terms": TEXT, "privacy": TEXT, "imprint": TEXT, "pricing": TEXT, "download": TEXT,
                    "changelog": TEXT, "docs": TEXT}),
    "social": (LIST, None),
    "created": (TEXT, None),
    "expires": (TEXT, None),
    "online_since": (TEXT, None),
    "hosting": (MAP, {"ip": TEXT, "flag": TEXT, "country": TEXT, "anycast": BOOL, "asn": TEXT, "org": TEXT}),
    "http": (INT, None),
    "sources": (LIST, None),
    "last_checked": (TEXT, None),
}
REQUIRED = ("name", "kind", "status")
KINDS = ("browser", "cloud-phone")
STATUSES = ("checked", "auto", "pending")
ENGINES = ("chromium", "firefox", "webkit")
PLATFORMS = ("windows", "macos", "linux", "android", "ios", "web")
STORAGE = ("cloud", "local", "both")
FLOW = {"kind", "engine", "platforms", "android", "domains", "payment"}  # short lists written on one line
FLOW_MAPS = {"cores", "hosting", "release"}  # maps written on one line
DATES = ("pushed", "created", "expires", "online_since", "last_checked")
ALLIANCE = {5: "Five Eyes", 9: "Nine Eyes", 14: "Fourteen Eyes"}
# Five / Nine / Fourteen Eyes membership by country (the same grouping as eMailCompare and xmppDB)
EYES = {"United States": 5, "United Kingdom": 5, "Canada": 5, "Australia": 5, "New Zealand": 5,
        "Denmark": 9, "France": 9, "Netherlands": 9, "Norway": 9,
        "Belgium": 14, "Germany": 14, "Italy": 14, "Spain": 14, "Sweden": 14}
ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH = re.compile(r"^\d{4}-\d{2}(?:-\d{2})?$")

# One-line strings written in quotes although PyYAML (YAML 1.1) would leave them plain: everything a YAML 1.2
# parser such as Hugo's might read as a number, boolean or null (the rule of eMailCompare and xmppDB).
QUOTE = re.compile(r"^(?:[-+]?\.?[0-9]|[-+]?\.(?:inf|Inf|INF|nan|NaN|NAN)$"
                   r"|(?:null|Null|NULL|~|true|True|TRUE|false|False|FALSE|yes|Yes|YES|no|No|NO|on|On|ON|off|Off|OFF)$)")


class _Flow(list):
    """A list written on one line: [a, b]."""


class _FlowMap(dict):
    """A map written on one line: {a: 1, b: 2}."""


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper, s):
    if "\n" in s or any(c in s for c in ("\x85", " ", " ", "\r")):
        return dumper.represent_scalar("tag:yaml.org,2002:str", s, style='"')
    if QUOTE.match(s):
        return dumper.represent_scalar("tag:yaml.org,2002:str", s, style="'")
    return dumper.represent_scalar("tag:yaml.org,2002:str", s)


_Dumper.add_representer(str, _str)
_Dumper.add_representer(_Flow, lambda d, v: d.represent_sequence("tag:yaml.org,2002:seq", v, flow_style=True))
_Dumper.add_representer(_FlowMap, lambda d, m: d.represent_mapping("tag:yaml.org,2002:map", m.items(),
                                                                   flow_style=True))
_Dumper.add_representer(dict, lambda d, m: d.represent_mapping("tag:yaml.org,2002:map", m.items()))


class _Loader(yaml.SafeLoader):
    """Reads YAML the way Hugo (a YAML 1.2 parser) does: no dates, no yes/no/on/off booleans, no sexagesimal
    numbers; those stay text."""


_Loader.yaml_implicit_resolvers = {}
for _tag, _regexp, _first in (
        ("null", r"^(?:~|null|Null|NULL|)$", ["~", "n", "N", ""]),
        ("bool", r"^(?:true|True|TRUE|false|False|FALSE)$", list("tTfF")),
        ("int", r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$", list("-+0123456789")),
        ("float", r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?|[-+]?\.(?:inf|Inf|INF)"
                  r"|\.(?:nan|NaN|NAN))$", list("-+0123456789."))):
    _Loader.add_implicit_resolver("tag:yaml.org,2002:" + _tag, re.compile(_regexp), _first)


def _empty(v):
    return v is None or v == "" or v == [] or v == {}


def _check_value(where, kind, v):
    if kind == TEXT and not isinstance(v, str):
        return f"{where} must be text"
    if kind == BOOL and not isinstance(v, bool):
        return f"{where} must be true or false"
    if kind == INT and (isinstance(v, bool) or not isinstance(v, int)):
        return f"{where} must be a whole number"
    if kind == LIST and not (isinstance(v, list) and all(isinstance(x, str) and x for x in v)):
        return f"{where} must be a list of text"
    return None


def _check_map(where, sub, m, out):
    if not isinstance(m, dict):
        out.append(f"{where} must be a map")
        return
    for k, v in m.items():
        if k not in sub:
            out.append(f"unknown field {where}.{k} (fields: data/README.md)")
        elif _empty(v):
            out.append(f"{where}.{k} is empty; leave the field out instead")
        else:
            p = _check_value(f"{where}.{k}", sub[k], v)
            if p:
                out.append(p)


def check(rec):
    """Problems of a record as text, [] when it is fine. Checks field names, types and values."""
    if not isinstance(rec, dict):
        return ["the file is not a mapping of fields"]
    out = []
    for k, v in rec.items():
        if k.startswith("_"):
            continue
        if k not in FIELDS:
            out.append(f"unknown field {k!r} (fields: data/README.md)")
            continue
        if _empty(v):
            out.append(f"{k} is empty; leave the field out instead")
            continue
        kind, sub = FIELDS[k]
        if kind == MAP:
            _check_map(k, sub, v, out)
        elif kind == MAPS:
            if not isinstance(v, list):
                out.append(f"{k} must be a list of maps")
                continue
            for i, m in enumerate(v):
                _check_map(f"{k}[{i}]", sub, m, out)
        else:
            p = _check_value(k, kind, v)
            if p:
                out.append(p)
    for k in REQUIRED:
        if _empty(rec.get(k)):
            out.append(f"{k} is required")
    for field, allowed in (("kind", KINDS), ("engine", ENGINES), ("platforms", PLATFORMS)):
        for x in rec.get(field) or []:
            if isinstance(x, str) and x not in allowed:
                out.append(f"{field}: unknown value {x!r} (one of {', '.join(allowed)})")
    for i, c in enumerate(rec.get("cores") or []):
        if isinstance(c, dict):
            if c.get("engine") not in ENGINES:
                out.append(f"cores[{i}].engine must be one of {', '.join(ENGINES)}")
            if not re.match(r"^\d+", str(c.get("version") or "")):
                out.append(f"cores[{i}].version must start with the major version number")
    if "status" in rec and rec["status"] not in STATUSES:
        out.append(f"status must be one of {', '.join(STATUSES)}")
    if "storage" in rec and rec["storage"] not in STORAGE:
        out.append(f"storage must be one of {', '.join(STORAGE)}")
    if "alliance" in rec and rec["alliance"] not in ALLIANCE:
        out.append("alliance must be 5, 9 or 14")
    if rec.get("dead") is False:
        out.append("dead: false is the default; leave the field out")
    if rec.get("successor") and not rec.get("dead"):
        out.append("successor is only for products that are gone (dead: true)")
    if rec.get("status") == "checked" and not rec.get("tests"):
        out.append("status checked needs the tests block (what was tested by hand)")
    for k in DATES:
        if isinstance(rec.get(k), str) and not DATE.match(rec[k]):
            out.append(f"{k} must be a date YYYY-MM-DD")
    for k in ("release", "tests"):
        d = (rec.get(k) or {}).get("date") if isinstance(rec.get(k), dict) else None
        if isinstance(d, str) and not DATE.match(d):
            out.append(f"{k}.date must be a date YYYY-MM-DD")
    for i, inc in enumerate(rec.get("incidents") or []):
        if isinstance(inc, dict) and not MONTH.match(str(inc.get("date") or "")):
            out.append(f"incidents[{i}].date must be YYYY-MM or YYYY-MM-DD")
        if isinstance(inc, dict) and not inc.get("links"):
            out.append(f"incidents[{i}] needs links to its sources")
    for k in ("website", "repo"):
        if isinstance(rec.get(k), str) and not rec[k].startswith(("https://", "http://")):
            out.append(f"{k} must be a URL")
    return out


def _ordered(rec):
    out = {}
    for k, (kind, sub) in FIELDS.items():
        v = rec.get(k)
        if _empty(v):
            continue
        if kind == MAP:
            v = {sk: v[sk] for sk in sub if not _empty(v.get(sk))}
            v = {sk: (_Flow(x) if isinstance(x, list) else x) for sk, x in v.items()}
            v = _FlowMap(v) if k in FLOW_MAPS else v
        elif kind == MAPS:
            items = []
            for m in v:
                m = {sk: m[sk] for sk in sub if not _empty(m.get(sk))}
                m = {sk: (_Flow(x) if isinstance(x, list) else x) for sk, x in m.items()}
                items.append(_FlowMap(m) if k in FLOW_MAPS else m)
            v = items
        elif k in FLOW:
            v = _Flow(v)
        out[k] = v
    return out


def dumps(rec):
    clean = {k: v for k, v in rec.items() if not k.startswith("_")}
    problems = check(clean)
    if problems:
        raise ValueError(f"{rec.get('_id') or rec.get('name')}: " + "; ".join(problems))
    text = yaml.dump(_ordered(clean), Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=4096,
                     default_flow_style=False)
    return HEADER + text


def loads(text):
    return yaml.load(text, Loader=_Loader)  # noqa: S506  (a SafeLoader subclass)


def path(pid, directory=None):
    return os.path.join(directory or DIR, pid + ".yaml")


def load(pid, directory=None):
    with open(path(pid, directory), encoding="utf-8") as f:
        rec = loads(f.read())
    rec["_id"] = pid
    return rec


def load_all(directory=None):
    recs = []
    for p in glob.glob(os.path.join(directory or DIR, "*.yaml")):
        with open(p, encoding="utf-8") as f:
            rec = loads(f.read())
        if not isinstance(rec, dict):
            raise ValueError(f"{p}: not a YAML mapping of fields")
        rec["_id"] = os.path.basename(p)[:-5]
        recs.append(rec)
    recs.sort(key=lambda r: (str(r.get("name", "")).lower(), r["_id"]))
    return recs


def _strip(rec):
    rec = {k: v for k, v in rec.items() if not k.startswith("_") and not _empty(v)}
    for k, (kind, sub) in FIELDS.items():
        if kind == MAP and isinstance(rec.get(k), dict):
            rec[k] = {sk: x for sk, x in rec[k].items() if not _empty(x)}
            if not rec[k]:
                del rec[k]
        elif kind == MAPS and isinstance(rec.get(k), list):
            rec[k] = [{sk: x for sk, x in m.items() if not _empty(x)} for m in rec[k]]
    if rec.get("dead") is False:
        del rec["dead"]
    return rec


def save(pid, rec, directory=None):
    """Write a record; refuses a bad id, unknown fields and text that does not read back to the same record."""
    if not ID.match(pid):
        raise ValueError(f"{pid}: an id is lower-case letters, digits and single dashes")
    rec = _strip(rec)
    text = dumps(rec)
    if loads(text) != rec:
        raise ValueError(f"{pid}: the YAML text would not read back to the same record")
    os.makedirs(directory or DIR, exist_ok=True)
    with open(path(pid, directory), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def upstream():
    """{'chrome': {'version', 'date'}, 'firefox': {'version', 'esr', 'date'}} from data/upstream.yaml."""
    with open(UPSTREAM, encoding="utf-8") as f:
        return loads(f.read()) or {}


def major(version):
    m = re.match(r"^(\d+)", str(version or ""))
    return int(m.group(1)) if m else None


def lag(core, up):
    """Major versions the core is behind the current stable Chrome (chromium) or Firefox (firefox) release."""
    ref = {"chromium": "chrome", "firefox": "firefox"}.get(core.get("engine"))
    have, cur = major(core.get("version")), major(((up or {}).get(ref) or {}).get("version"))
    if ref is None or have is None or cur is None:
        return None
    return max(cur - have, 0)


def is_esr(core, up):
    """A Firefox core on the major version of the current Firefox ESR."""
    esr = major(((up or {}).get("firefox") or {}).get("esr"))
    return core.get("engine") == "firefox" and esr is not None and major(core.get("version")) == esr


def flag(cc):
    cc = (cc or "").upper()
    if len(cc) != 2 or not cc.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in cc)
