#!/usr/bin/env python3
"""Google Trends reachability smoke test.

Run this INSIDE the environment you plan to use (GitHub Codespace, Colab, or your
laptop) to find out whether a live Google Trends pull actually works from that
network. Codespaces and Colab egress from cloud datacenter IPs (Azure, Google),
which Google Trends often rate-limits hard, so the answer can differ from your laptop.

    python scripts/gt_smoke_test.py

Standard library only: it runs on the bare course container before any pip install,
and it does NOT need pytrends. It replicates what pytrends does under the hood
(cookie -> token -> data) with a paced retry, and prints a clear verdict.
"""
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122 Safari/537.36")


def _opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA),
                     ("Accept-Language", "en-US,en;q=0.9"),
                     ("Referer", "https://trends.google.com/")]
    return op, cj


def _get(op, url, tries=4, base=12):
    for i in range(tries):
        try:
            r = op.open(url, timeout=25)
            return r.getcode(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                wait = base * (i + 1)
                print(f"    429 (rate-limited); waiting {wait}s and retrying "
                      f"({i + 1}/{tries})...")
                time.sleep(wait)
                continue
            return e.code, ""
        except Exception as e:  # noqa: BLE001
            return -1, str(e)
    return 429, ""


def environment():
    print("== Environment ==")
    in_cs = os.environ.get("CODESPACES") == "true"
    print("  hostname   :", socket.gethostname())
    print("  Codespace  :", "YES" if in_cs else "no",
          f"(name={os.environ.get('CODESPACE_NAME')})" if in_cs else "")
    op, _ = _opener()
    try:
        ip = json.loads(_get(op, "https://ipinfo.io/json")[1])
        org = ip.get("org", "?")
        print("  egress IP  :", ip.get("ip", "?"), "|", ip.get("city", "?"),
              ip.get("region", "?"), ip.get("country", "?"))
        print("  network    :", org)
        cloud = any(k in org.lower() for k in
                    ("microsoft", "azure", "google", "amazon", "aws", "cloud"))
        if cloud:
            print("  -> This looks like a CLOUD/datacenter IP. Google Trends "
                  "commonly rate-limits these.")
        return cloud
    except Exception as e:  # noqa: BLE001
        print("  (could not determine egress IP:", e, ")")
        return None


def trends_pull():
    print("\n== Google Trends live pull (dengue, geo=MX, today 3-m) ==")
    op, _ = _opener()
    c, _ = _get(op, "https://trends.google.com/?geo=MX")
    print("  1) homepage / cookie :", c)
    req = {"comparisonItem": [{"keyword": "dengue", "geo": "MX", "time": "today 3-m"}],
           "category": 0, "property": ""}
    q = urllib.parse.urlencode({"hl": "en-US", "tz": "360", "req": json.dumps(req)})
    c, body = _get(op, "https://trends.google.com/trends/api/explore?" + q)
    print("  2) token (api/explore):", c)
    if c != 200:
        return False
    try:
        w = next(x for x in json.loads(body[body.find("{"):])["widgets"]
                 if x["id"] == "TIMESERIES")
    except Exception as e:  # noqa: BLE001
        print("     could not parse token:", e)
        return False
    time.sleep(6)
    q2 = urllib.parse.urlencode({"hl": "en-US", "tz": "360",
                                 "req": json.dumps(w["request"]), "token": w["token"]})
    c, body = _get(op, "https://trends.google.com/trends/api/widgetdata/multiline?" + q2)
    print("  3) data (widgetdata) :", c)
    if c != 200:
        return False
    pts = json.loads(body[body.find("{"):])["default"]["timelineData"]
    print(f"     SUCCESS: {len(pts)} points; last = "
          f"{pts[-1]['formattedTime']} -> {pts[-1]['value']}")
    return True


def main():
    cloud = environment()
    ok = trends_pull()
    print("\n== Verdict ==")
    if ok:
        print("  Live Google Trends pull WORKED from this network.")
        print("  Keep pulls small and paced; the whole room bursting at once can still 429.")
    else:
        print("  Live Google Trends pull did NOT complete (rate-limited or blocked).")
        if cloud:
            print("  This is the expected Codespaces/Colab outcome: cloud IPs get throttled.")
        print("  Use the cached data (Plan B) for the exercise. For a genuinely live pull,")
        print("  run from a laptop/campus network, or refresh the cache before class with")
        print("  refresh_cache.py on an ordinary connection.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
