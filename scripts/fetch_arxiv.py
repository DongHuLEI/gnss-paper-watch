#!/usr/bin/env python3
"""Fetch and rank recent arXiv candidates for the four site domains.

Usage:
    python3 scripts/fetch_arxiv.py --days 14 --max 40
    python3 scripts/fetch_arxiv.py --days 30 --output data/candidates.json

This script only fetches metadata and produces a candidate list. Chinese
summaries are intentionally left to manual review before they enter
data/editions/<date>.json. scripts/daily_update.py builds an automatic
edition from these candidates.
"""

import argparse
import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITIONS = ROOT / "data" / "editions"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

QUERIES = {
    "gnss": '(abs:"GNSS" OR abs:"GPS" OR abs:"BDS") AND (abs:"precise point positioning" OR abs:"PPP" OR abs:"RTK" OR abs:"ambiguity resolution" OR abs:"GNSS positioning" OR abs:"CORS")',
    "iono": '(abs:"ionosphere" OR abs:"ionospheric" OR abs:"ROTI" OR abs:"total electron content" OR abs:"scintillation") AND (abs:"GNSS" OR abs:"TEC" OR abs:"navigation" OR abs:"space weather")',
    "ml": '(abs:"ionosphere" OR abs:"ionospheric" OR abs:"TEC" OR abs:"ROTI") AND (abs:"deep learning" OR abs:"neural network" OR abs:"transformer" OR abs:"graph neural" OR abs:"forecast")',
    "perception": '(abs:"GNSS" OR abs:"GPS") AND (abs:"multipath" OR abs:"NLOS" OR abs:"interference" OR abs:"jamming" OR abs:"spoofing" OR abs:"integrity" OR abs:"quality assessment" OR abs:"robust estimation")',
}

DOMAIN_TERMS = {
    "gnss": ["precise point positioning", "ppp", "ppp-rtk", "rtk", "ambiguity", "cors", "gnss positioning", "bds", "beidou", "leo navigation", "convergence"],
    "iono": ["ionosphere", "ionospheric", "roti", "total electron content", "tec", "scintillation", "storm", "sed", "plasmasphere", "doris", "space weather"],
    "ml": ["deep learning", "neural network", "transformer", "graph neural", "forecast", "prediction", "lstm", "attention", "explainable", "uncertainty"],
    "perception": ["multipath", "nlos", "interference", "jamming", "spoofing", "integrity", "quality", "robust", "receiver", "signal processing", "factor graph"],
}


def existing_ids():
    ids = set()
    for path in sorted(EDITIONS.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        ids.update(paper["id"].split("v")[0] for paper in data.get("papers", []))
    return ids


def fetch(query, max_results=60):
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "gnss-paper-radar/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    items = []
    for entry in root.findall("a:entry", NS):
        raw_id = entry.find("a:id", NS).text.rsplit("/abs/", 1)[-1]
        base_id = re.sub(r"v\d+$", "", raw_id)
        title = " ".join(entry.find("a:title", NS).text.split())
        summary = " ".join(entry.find("a:summary", NS).text.split())
        published = entry.find("a:published", NS).text[:10]
        authors = [node.find("a:name", NS).text for node in entry.findall("a:author", NS)]
        cats = [node.get("term") for node in entry.findall("a:category", NS)]
        items.append(
            {
                "id": base_id,
                "version": raw_id[len(base_id) :],
                "title": title,
                "abstract": summary,
                "date": published,
                "authors": authors,
                "cats": cats,
            }
        )
    return items


def domain_gate(haystack, domain):
    """Require a core domain anchor before keyword scoring."""
    if domain == "gnss":
        return any(term in haystack for term in ("gnss", "gps", "bds", "beidou", "precise point positioning", "ppp", "rtk", "cors"))
    if domain == "iono":
        core = any(term in haystack for term in ("ionosphere", "ionospheric", "total electron content", "tec", "roti"))
        return core and any(term in haystack for term in ("gnss", "gps", "navigation", "radio", "space weather"))
    if domain == "ml":
        return any(term in haystack for term in ("ionosphere", "ionospheric", "tec", "roti", "total electron content")) and any(
            term in haystack for term in ("deep learning", "neural", "transformer", "graph", "forecast", "prediction", "machine learning")
        )
    if domain == "perception":
        core = any(term in haystack for term in ("gnss", "gps", "bds", "beidou", "satellite navigation"))
        return core and any(
            term in haystack
            for term in ("multipath", "nlos", "interference", "jamming", "spoofing", "integrity", "observation quality", "quality assessment", "robust estimation", "factor graph")
        )
    return False


def score_item(item, domain):
    haystack = (item["title"] + " " + item["abstract"]).lower()
    if any(term in haystack for term in ("maritime cyber", "forensically sound", "dark matter", "calorimeter")):
        return 0, []
    if not domain_gate(haystack, domain):
        return 0, []
    title = item["title"].lower()
    hits = [term for term in DOMAIN_TERMS[domain] if term in haystack]
    score = 24 + 9 * len(set(hits))
    title_anchor = any(term in title for term in ("gnss", "gps", "ionosphere", "ionospheric", "tec", "roti", "scintillation", "ppp", "rtk"))
    if title_anchor:
        score += 12
    elif domain in ("iono", "perception"):
        score = min(score, 58)
    if len(set(hits)) >= 4:
        score += 8
    return min(100, score), sorted(set(hits))


def main():
    parser = argparse.ArgumentParser(description="Fetch recent arXiv candidates for the paper radar.")
    parser.add_argument("--days", type=int, default=21, help="keep papers submitted within N days (default 21)")
    parser.add_argument("--max", type=int, default=60, help="max results per query (default 60)")
    parser.add_argument("--min-score", type=int, default=45, help="drop candidates below this relevance score")
    parser.add_argument("--output", default="", help="output JSON path (default data/candidates-YYYY-MM-DD.json)")
    args = parser.parse_args()

    cutoff = dt.date.today() - dt.timedelta(days=args.days)
    known = existing_ids()
    candidates = {}

    for domain, query in QUERIES.items():
        print("query", domain, "...", flush=True)
        try:
            items = parse(fetch(query, args.max))
        except Exception as exc:  # network/API errors should not kill the other domains
            print("  failed:", exc)
            continue
        for item in items:
            try:
                published = dt.datetime.strptime(item["date"], "%Y-%m-%d").date()
            except ValueError:
                continue
            if published < cutoff or item["id"] in known:
                continue
            score, hits = score_item(item, domain)
            if score < args.min_score:
                continue
            if item["id"] not in candidates or score > candidates[item["id"]]["score"]:
                candidates[item["id"]] = {
                    "id": item["id"],
                    "title": item["title"],
                    "date": item["date"],
                    "authors": item["authors"],
                    "cats": item["cats"],
                    "abstract": item["abstract"],
                    "domain": domain,
                    "score": score,
                    "matched_terms": hits,
                    "abs_url": "https://arxiv.org/abs/" + item["id"],
                    "pdf_url": "https://arxiv.org/pdf/" + item["id"],
                }
        time.sleep(3)

    ranked = sorted(candidates.values(), key=lambda item: (-item["score"], item["date"]), reverse=False)
    output = Path(args.output) if args.output else ROOT / "data" / ("candidates-%s.json" % dt.date.today().isoformat())
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "days": args.days,
                "count": len(ranked),
                "candidates": ranked,
            },
            handle,
            ensure_ascii=False,
            indent=1,
        )
    print("wrote", len(ranked), "candidates to", output)
    for item in ranked[:15]:
        print(item["score"], item["date"], item["domain"], item["id"], item["title"][:96])


if __name__ == "__main__":
    main()
