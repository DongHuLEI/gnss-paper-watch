#!/usr/bin/env python3
"""Verify the deployed public files and reject source-directory publication."""

import argparse
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from build_site import Site
from radar_config import ROOT


def check(base_url, files, excluded, timeout, nonce):
    errors = []
    for name in list(files) + list(excluded):
        url = urllib.parse.urljoin(base_url, name)
        url += "?" + urllib.parse.urlencode({"radar_deploy_check": nonce})
        request = urllib.request.Request(url, headers={
            "User-Agent": "gnss-radar-deployment-check/2.0",
            "Cache-Control": "no-cache",
        })
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.getcode()
                body = response.read(4 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            status, body = error.code, b""
        except (urllib.error.URLError, OSError) as error:
            errors.append("%s: %s" % (name, type(error).__name__))
            continue
        if name in excluded:
            if status != 404:
                errors.append("%s: source file must return 404, got %s" % (name, status))
        elif status != 200:
            errors.append("%s: expected HTTP 200, got %s" % (name, status))
        elif body != files[name]:
            errors.append("%s: published content does not match this build" % name)
    return errors


def main():
    site = Site()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=site.settings["site"]["url"])
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--delay", type=float, default=15)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    parsed = urllib.parse.urlsplit(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error("url must be an HTTP(S) site base without credentials, query or fragment")
    if not 1 <= args.attempts <= 5 or args.delay < 0 or args.timeout <= 0:
        parser.error("invalid verification retry limits")
    paper = next((paper for paper in site.papers if paper["status"] == "ai"), site.papers[0])
    paths = ["index.html", "library/index.html", "archive/index.html", "learn/index.html", "about/index.html",
             "daily/%s/index.html" % site.latest["edition"]["date"], "papers/%s/index.html" % paper["slug"],
             "assets/app.css", "assets/app.js"]
    if site.deep_reads:
        from deep_reading import equation_asset
        paths.extend("papers/%s/index.html" % site.catalogue[paper_id]["slug"] for paper_id in site.deep_reads)
        paths.extend(("assets/deep-reading.css", "assets/deep-reading.js", "assets/deep-reading/LICENSE.txt"))
        for data in site.deep_reads.values():
            for equation in data["equations"]:
                paths.extend(equation_asset(data, equation, field) for field in ("mathml", "mathml_second") if equation.get(field))
    files = {name: (ROOT / name).read_bytes() for name in dict.fromkeys(paths)}
    excluded = ("scripts/daily_update.py", "scripts/deep_reading.py", "scripts/reading_pipeline.py", "scripts/automation_gate.py", "data/status.json", "data/reading_queue.json", "data/backfill.json", "README.md", ".agents/skills/paper-deep-reading/SKILL.md")
    excluded += tuple("data/deep_reads/%s.json" % paper_id for paper_id in site.deep_reads)
    base_url = args.url.rstrip("/") + "/"
    errors = []
    for attempt in range(args.attempts):
        nonce = "%s-%s" % (time.time_ns() if hasattr(time, "time_ns") else int(time.time() * 1000000), attempt)
        errors = check(base_url, files, excluded, args.timeout, nonce)
        if not errors:
            print("verified %d public pages/assets and %d excluded source paths at %s" % (len(files), len(excluded), base_url))
            return 0
        for error in errors:
            print("deployment check: " + error, file=sys.stderr, flush=True)
        if attempt + 1 < args.attempts:
            time.sleep(args.delay)
    return 1


if __name__ == "__main__":
    sys.exit(main())
