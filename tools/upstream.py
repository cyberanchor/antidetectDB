#!/usr/bin/env python3
"""Write data/upstream.yaml: the current stable Chrome and Firefox versions, the yardstick for the core lag.

  chrome   Google's VersionHistory API, Windows stable channel: the release that serves the largest share of users
           (an early-stable build that reaches 0.5 % of users a week ahead does not count yet)
  firefox  Mozilla's product-details: the latest release and the ESR

usage: python3 tools/upstream.py [--check]   (--check: print the versions, write nothing)
"""
import datetime
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addata  # noqa: E402

CHROME = ("https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions/all/releases"
          "?filter=endtime=none")
FIREFOX = "https://product-details.mozilla.org/1.0/firefox_versions.json"
UA = os.environ.get("ADB_UA", "Mozilla/5.0 (compatible; adb-collector/1.0)")
HEADER = ("# Current stable releases of the upstream browsers, the yardstick for the core lag on the site and in\n"
          "# the README. Written by tools/upstream.py; do not edit by hand.\n")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310  (fixed https URLs)
        return json.load(r)


def main():
    today = datetime.date.today().isoformat()
    serving = get(CHROME)["releases"]
    if not serving:
        raise SystemExit("VersionHistory API: no Chrome stable release is serving")

    def key(r):
        return (r.get("fraction") or 0, [int(x) for x in r["version"].split(".")])

    chrome = max(serving, key=key)["version"]
    ff = get(FIREFOX)
    data = {
        "chrome": {"version": chrome, "date": today, "source": CHROME},
        "firefox": {"version": ff["LATEST_FIREFOX_VERSION"], "esr": ff["FIREFOX_ESR"], "date": today,
                    "source": FIREFOX},
    }
    if "--check" in sys.argv:
        print(json.dumps(data, indent=1))
        return
    text = HEADER + "".join(
        f"{k}: {{{', '.join(f'{sk}: ' + repr(str(sv)) for sk, sv in v.items())}}}\n" for k, v in data.items())
    if addata.loads(text) != data:
        raise SystemExit("upstream.yaml would not read back to the same data")
    with open(addata.UPSTREAM, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"{addata.UPSTREAM}: Chrome {chrome}, Firefox {data['firefox']['version']} (ESR {data['firefox']['esr']})")


if __name__ == "__main__":
    main()
