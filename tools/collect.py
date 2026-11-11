#!/usr/bin/env python3
"""Automatic checks of the products in data/products/ and the fields they write.

  web      http          status code of the website (0: no answer); a bot check (403/503) still counts as an answer
  hosting  hosting       first IPv4 address of the website's host: country, network and organisation (ip-api.com);
                         an anycast CDN address (Cloudflare, Fastly, Akamai, CloudFront) gets anycast: true, no country
  rdap     created, expires   registration and expiry date of the website's domain (RDAP, rdap.org)
  wayback  online_since  first capture of the domain in the Wayback Machine
           (both skipped for sites on shared domains such as github.io)
  github   stars, pushed, license, release   for products with a GitHub repo (set GITHUB_TOKEN for more requests)
  and      last_checked  when at least one check ran

A check that fails keeps the old value. No account is created, no software is downloaded.

usage: python3 tools/collect.py [--all | ID...] [--only web,hosting,rdap,wayback,github] [--dry-run]
"""
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addata  # noqa: E402

UA = os.environ.get("ADB_UA", "Mozilla/5.0 (compatible; adb-collector/1.0)")
STEPS = ("web", "hosting", "rdap", "wayback", "github")
# Networks that announce the same addresses from many places (anycast CDNs): their addresses have no country.
ANYCAST_ASN = {"AS13335", "AS209242", "AS54113", "AS16625", "AS20940"}  # Cloudflare (2), Fastly, Akamai (2)
ANYCAST_ORG = ("CloudFront (GLOBAL)", "Global Accelerator")
# Shared hosting domains: the registration date and first capture of github.io say nothing about one project.
SHARED = {"github.io", "gitlab.io", "vercel.app", "netlify.app", "pages.dev", "web.app", "firebaseapp.com",
          "gitbook.io", "readthedocs.io"}
SUFFIX2 = {"com.cn", "net.cn", "org.cn", "co.uk", "com.au", "com.br", "com.ua", "co.jp", "com.tw", "com.hk",
           "com.vn", "com.ru", "com.tr", "co.kr", "com.sg"}


def request(url, data=None, headers=None, timeout=30):
    h = {"User-Agent": UA, "Accept-Language": "en"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310  (http/https URLs from the records)


def get_json(url, headers=None):
    with request(url, headers=headers) as r:
        return json.load(r)


def domain_of(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in SUFFIX2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def check_web(rec):
    try:
        with request(rec["website"], timeout=25) as r:
            return {"http": r.status}
    except urllib.error.HTTPError as e:
        return {"http": e.code}
    except Exception:  # noqa: BLE001  (DNS, TLS, timeout: no answer)
        return {"http": 0}


def resolve(host):
    out = subprocess.run(["dig", "+short", "+time=5", "+tries=2", "A", host], capture_output=True, text=True).stdout
    for line in out.split():
        if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", line):
            return line
    return None


def check_hosting(recs):
    """{id: {'hosting': {...}}} for every record with a website, in one ip-api.com batch per 100 addresses."""
    ips = {}
    for r in recs:
        if r.get("website"):
            ip = resolve(urllib.parse.urlsplit(r["website"]).hostname)
            if ip:
                ips[r["_id"]] = ip
    out, todo = {}, sorted(set(ips.values()))
    info = {}
    for i in range(0, len(todo), 100):
        body = json.dumps([{"query": ip, "fields": "status,country,countryCode,as,org,query"}
                           for ip in todo[i:i + 100]]).encode()
        try:
            with request("http://ip-api.com/batch", data=body, headers={"Content-Type": "application/json"}) as r:
                for row in json.load(r):
                    if row.get("status") == "success":
                        info[row["query"]] = row
        except Exception as e:  # noqa: BLE001
            print(f"  hosting: ip-api.com failed: {e}", file=sys.stderr)
        time.sleep(4)
    for pid, ip in ips.items():
        row = info.get(ip)
        if row:
            asn = row.get("as") or ""
            anycast = asn.split(" ")[0] in ANYCAST_ASN or any(o in (row.get("org") or "") for o in ANYCAST_ORG)
            if anycast:  # a CDN edge: the lookup's country is only where the database places the range
                out[pid] = {"hosting": {"ip": ip, "anycast": True, "asn": asn, "org": row.get("org")}}
            else:
                out[pid] = {"hosting": {"ip": ip, "flag": addata.flag(row.get("countryCode")),
                                        "country": row.get("country"), "asn": asn, "org": row.get("org")}}
    return out


def check_rdap(rec):
    try:
        data = get_json("https://rdap.org/domain/" + domain_of(rec["website"]))
    except Exception:  # noqa: BLE001  (no RDAP for this TLD, or not found)
        return {}
    out = {}
    for ev in data.get("events") or []:
        d = (ev.get("eventDate") or "")[:10]
        if not addata.DATE.match(d):
            continue
        if ev.get("eventAction") == "registration":
            out["created"] = d
        elif ev.get("eventAction") == "expiration":
            out["expires"] = d
    return out


def check_wayback(rec):
    url = ("https://web.archive.org/cdx/search/cdx?limit=1&fl=timestamp&url="
           + urllib.parse.quote(domain_of(rec["website"])))
    try:
        with request(url, timeout=60) as r:
            ts = r.read().decode().strip()
    except Exception:  # noqa: BLE001
        return {}
    if re.fullmatch(r"\d{14}", ts):
        return {"online_since": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"}
    return {}


def check_github(rec):
    m = re.match(r"^https://github\.com/([^/]+)/([^/#?]+)", rec.get("repo") or "")
    if not m:
        return {}
    api = f"https://api.github.com/repos/{m.group(1)}/{m.group(2)}"
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    try:
        repo = get_json(api, headers)
    except Exception as e:  # noqa: BLE001
        print(f"  github {m.group(1)}/{m.group(2)}: {e}", file=sys.stderr)
        return {}
    out = {"stars": repo.get("stargazers_count"), "pushed": (repo.get("pushed_at") or "")[:10] or None}
    lic = (repo.get("license") or {}).get("spdx_id")
    if lic and lic != "NOASSERTION":
        out["license"] = lic
    try:
        rel = get_json(api + "/releases/latest", headers)
        out["release"] = {"version": rel.get("tag_name"), "date": (rel.get("published_at") or "")[:10] or None}
    except Exception:  # noqa: BLE001  (no releases)
        pass
    return {k: v for k, v in out.items() if v not in (None, "", {})}


def main():
    args = sys.argv[1:]
    only = set(STEPS)
    if "--only" in args:
        i = args.index("--only")
        only = set(args[i + 1].split(","))
        del args[i:i + 2]
        if not only <= set(STEPS):
            raise SystemExit(f"--only: steps are {', '.join(STEPS)}")
    dry = "--dry-run" in args
    ids = [a for a in args if not a.startswith("--")]
    recs = addata.load_all()
    if ids:
        known = {r["_id"] for r in recs}
        for pid in ids:
            if pid not in known:
                raise SystemExit(f"{pid}: no data/products/{pid}.yaml")
        recs = [r for r in recs if r["_id"] in ids]
    elif "--all" not in args:
        raise SystemExit(__doc__)
    today = datetime.date.today().isoformat()
    results = {r["_id"]: {} for r in recs}
    if "hosting" in only:
        print("hosting: resolving and looking up the addresses", flush=True)
        for pid, upd in check_hosting(recs).items():
            results[pid].update(upd)
    for r in recs:
        upd = results[r["_id"]]
        if r.get("website"):
            shared = domain_of(r["website"]) in SHARED
            if "web" in only:
                upd.update(check_web(r))
            if "rdap" in only and not shared:
                upd.update(check_rdap(r))
            if "wayback" in only and not shared:
                upd.update(check_wayback(r))
        if "github" in only:
            upd.update(check_github(r))
        if upd:
            upd["last_checked"] = today
        print(f"{r['_id']}: " + (", ".join(f"{k}={v}" for k, v in upd.items() if k != "last_checked") or "no result"),
              flush=True)
        if not dry and upd:
            rec = {k: v for k, v in r.items() if k != "_id"}
            rec.update(upd)
            addata.save(r["_id"], rec)


if __name__ == "__main__":
    main()
