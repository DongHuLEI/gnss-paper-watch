#!/usr/bin/env python3
"""Retrieve date-bounded arXiv metadata with multi-domain classification."""

import argparse
import datetime as dt
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from radar_config import (
    DATA, beijing_now, classify, known_ids, load_config, load_editions,
    utc_timestamp, write_json,
)

NS = {"a": "http://www.w3.org/2005/Atom"}
ARXIV_ID = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?$")
DOMAINS, LENSES, SETTINGS = load_config()
QUERIES = {key: value["query"] for key, value in DOMAINS.items()}
DOMAIN_TERMS = {key: value["terms"] for key, value in DOMAINS.items()}


def existing_ids():
    return known_ids(load_editions())


def fetch(query, max_results=60):
    return api_request({
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })


def fetch_by_ids(ids):
    ids = list(dict.fromkeys(value for value in ids if ARXIV_ID.match(value)))[:30]
    return parse(api_request({"id_list": ",".join(ids), "max_results": len(ids)})) if ids else []


def api_request(params):
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "gnss-ai-research-radar/2.0"})
    config = SETTINGS["retrieval"]
    for attempt in range(config["retries"] + 1):
        try:
            with urllib.request.urlopen(request, timeout=config["request_timeout"]) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise
            if attempt == config["retries"]:
                raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == config["retries"]:
                raise
        time.sleep(max(config["arxiv_interval_seconds"], 4 * (attempt + 1)))


def field(entry, name):
    node = entry.find("a:" + name, NS)
    return " ".join((node.text or "").split()) if node is not None else ""


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    if root.tag != "{http://www.w3.org/2005/Atom}feed":
        raise ValueError("arXiv returned a non-Atom response")
    items = []
    for entry in root.findall("a:entry", NS):
        raw_id = field(entry, "id").rsplit("/abs/", 1)[-1]
        if "api/errors" in raw_id:
            raise ValueError("arXiv rejected the query: " + field(entry, "summary")[:180])
        title = field(entry, "title")
        summary = field(entry, "summary")
        published = field(entry, "published")[:10]
        if not ARXIV_ID.match(raw_id) or not all((title, summary, published)):
            continue
        base_id = re.sub(r"v\d+$", "", raw_id)
        authors = [field(node, "name") for node in entry.findall("a:author", NS)]
        items.append({
            "id": base_id,
            "version": raw_id[len(base_id):],
            "title": title,
            "abstract": summary,
            "date": published,
            "updated": field(entry, "updated")[:10] or published,
            "authors": [name for name in authors if name],
            "cats": [node.get("term") for node in entry.findall("a:category", NS) if node.get("term")],
            "abs_url": "https://arxiv.org/abs/" + base_id,
            "pdf_url": "https://arxiv.org/pdf/" + base_id,
            "source": "arxiv",
        })
    return items


def score_item(item, domain):
    result = classify(item["title"], item["abstract"], DOMAINS, LENSES)
    return result["domain_scores"].get(domain, 0), [
        term for term in DOMAIN_TERMS.get(domain, [])
        if term in result["matched_terms"]
    ]


def collect_candidates(days=None, max_results=None, min_score=None, as_of=None, known=None, only=None):
    config = SETTINGS["retrieval"]
    days = config["days"] if days is None else days
    max_results = config["results_per_domain"] if max_results is None else max_results
    min_score = config["min_score"] if min_score is None else min_score
    as_of = as_of or beijing_now().date()
    if days < 1 or not 1 <= max_results <= 200 or not 0 <= min_score <= 100:
        raise ValueError("days must be positive, max must be 1..200 and min-score must be 0..100")
    cutoff = as_of - dt.timedelta(days=days)
    known = existing_ids() if known is None else known
    candidates = {}
    queries = []
    selected_domains = list(only or DOMAINS)
    for index, domain in enumerate(selected_domains):
        if domain not in QUERIES:
            raise ValueError("unknown domain: " + domain)
        if index:
            time.sleep(config["arxiv_interval_seconds"])
        query = "(%s) AND submittedDate:[%s0000 TO %s2359]" % (
            QUERIES[domain], cutoff.strftime("%Y%m%d"), as_of.strftime("%Y%m%d"),
        )
        print("query %s ..." % domain, flush=True)
        record = {"domain": domain, "status": "ok", "returned": 0, "accepted": 0}
        try:
            items = parse(fetch(query, max_results))
            record["returned"] = len(items)
            for item in items:
                try:
                    published = dt.datetime.strptime(item["date"], "%Y-%m-%d").date()
                except ValueError:
                    continue
                if not cutoff <= published <= as_of or item["id"] in known:
                    continue
                classification = classify(item["title"], item["abstract"], DOMAINS, LENSES)
                if classification["score"] < min_score:
                    continue
                item.update(classification)
                candidates[item["id"]] = item
                record["accepted"] += 1
        except Exception as exc:
            record.update(status="failed", error="%s: %s" % (type(exc).__name__, str(exc)[:240]))
            print("  retrieval failed for %s: %s" % (domain, record["error"]), file=sys.stderr)
        queries.append(record)
    failed = sum(item["status"] != "ok" for item in queries)
    status = "failed" if failed == len(queries) else ("partial" if failed else "ok")
    ranked = sorted(candidates.values(), key=lambda item: item["date"], reverse=True)
    ranked.sort(key=lambda item: -item["score"])
    return {
        "generated": utc_timestamp(),
        "as_of": as_of.isoformat(),
        "days": days,
        "status": status,
        "queries": queries,
        "count": len(ranked),
        "candidates": ranked,
    }


def main():
    config = SETTINGS["retrieval"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=config["days"])
    parser.add_argument("--max", type=int, default=config["results_per_domain"])
    parser.add_argument("--min-score", type=int, default=config["min_score"])
    parser.add_argument("--date", default="", help="upper bound date (Beijing by default)")
    parser.add_argument("--domain", choices=list(DOMAINS), action="append", help="optional subset of sources")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    as_of = dt.datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else beijing_now().date()
    result = collect_candidates(args.days, args.max, args.min_score, as_of=as_of, only=args.domain)
    output = Path(args.output) if args.output else DATA / ("candidates-%s.json" % as_of.isoformat())
    write_json(output, result)
    print("%s: wrote %d candidates to %s" % (result["status"], result["count"], output))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
