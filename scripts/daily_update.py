#!/usr/bin/env python3
"""Generate one automatic daily edition and publish it.

Usage:
    python3 scripts/daily_update.py                 # today (Beijing), build + push
    python3 scripts/daily_update.py --no-push       # build locally only
    python3 scripts/daily_update.py --date 2026-10-22 --per-domain 3
    python3 scripts/daily_update.py --force         # rebuild an existing date

Entries created here are marked "auto": they carry the arXiv title, abstract,
authors and categories, and are labelled 机器初筛 on the site. Chinese
interpretation is deliberately not invented by the script.
"""

import argparse
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITIONS = ROOT / "data" / "editions"
DOMAINS_FILE = ROOT / "data" / "domains.json"
FETCH = ROOT / "scripts" / "fetch_arxiv.py"
BUILD = ROOT / "scripts" / "build_site.py"

DOMAIN_ORDER = ["gnss", "iono", "ml", "perception"]

NOTE_ZH = "本条由每日脚本自动收录，未经人工解读。标题、作者、分类和下面的摘要是 arXiv 原文，方便你判断是否值得精读。"
NOTE_EN = "Machine-selected from arXiv, no human summary yet. Title, authors, categories and the abstract below are the original metadata."


def beijing_today():
    return (dt.datetime.utcnow() + dt.timedelta(hours=8)).date()


def load_domains():
    with DOMAINS_FILE.open(encoding="utf-8") as handle:
        return json.load(handle)["domains"]


def load_editions():
    seen = {}
    numbers = []
    ids = set()
    for path in sorted(EDITIONS.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        seen[data["edition"]["date"]] = path
        try:
            numbers.append(int(data["edition"]["number"]))
        except (TypeError, ValueError):
            pass
        ids.update(paper["id"].split("v")[0] for paper in data.get("papers", []))
    return seen, numbers, ids


def short(value, limit):
    value = " ".join(str(value).split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def first_sentence(abstract, limit=170):
    text = " ".join(abstract.split())
    cut = text.find(". ")
    if 40 < cut < limit:
        return text[: cut + 1]
    return short(text, limit)


def authors_of(names):
    if len(names) > 8:
        return names[:8] + ["et al."]
    return list(names)


def fetch_candidates(date_str, days, max_results, min_score):
    out = Path(tempfile.gettempdir()) / ("gnss-radar-candidates-%s.json" % date_str)
    cmd = [
        sys.executable,
        str(FETCH),
        "--days",
        str(days),
        "--max",
        str(max_results),
        "--min-score",
        str(min_score),
        "--output",
        str(out),
    ]
    print("$ " + " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0 or not out.exists():
        return []
    with out.open(encoding="utf-8") as handle:
        return json.load(handle).get("candidates", [])


def pick(candidates, per_domain, already):
    picked = []
    for domain in DOMAIN_ORDER:
        pool = [item for item in candidates if item["domain"] == domain and item["id"] not in already]
        pool.sort(key=lambda item: item["date"], reverse=True)
        pool.sort(key=lambda item: -item["score"])
        picked.extend(pool[:per_domain])
    picked.sort(key=lambda item: -item["score"])
    return picked


def make_paper(item):
    return {
        "id": item["id"],
        "slug": "arxiv-" + item["id"],
        "domain": item["domain"],
        "date": item["date"],
        "score": item["score"],
        "tier": "机器初筛",
        "auto": True,
        "title_zh": item["title"],
        "title_en": item["title"],
        "authors": authors_of(item.get("authors", [])),
        "cats": item.get("cats", [])[:3],
        "tags": item.get("matched_terms", [])[:4],
        "one_liner": first_sentence(item["abstract"]),
        "one_liner_en": first_sentence(item["abstract"]),
        "lead_zh": NOTE_ZH,
        "lead_en": NOTE_EN,
        "abstract_en": item["abstract"],
        "links": {
            "abs": "https://arxiv.org/abs/" + item["id"],
            "pdf": "https://arxiv.org/pdf/" + item["id"],
        },
    }


def make_edition(date_str, papers, domains, number):
    date = dt.datetime.strptime(date_str, "%Y-%m-%d")
    counts = {key: sum(1 for p in papers if p["domain"] == key) for key in DOMAIN_ORDER}
    covered = [key for key in DOMAIN_ORDER if counts[key]]
    top = papers[0]
    threads = []
    for key in covered:
        best = max((p for p in papers if p["domain"] == key), key=lambda p: p["score"])
        threads.append(
            {
                "domain": key,
                "title": domains[key]["label"] + " · " + str(counts[key]) + " 篇",
                "text": "最高匹配度 " + str(best["score"]) + "：" + short(best["title_en"], 96),
            }
        )
    stats = [
        {"value": str(len(papers)), "label": "本期篇数"},
        {"value": str(len(covered)), "label": "覆盖领域"},
        {"value": str(top["score"]), "label": "最高匹配度"},
        {"value": "AUTO", "label": "编选方式"},
    ]
    overview = [
        "本期共 " + str(len(papers)) + " 篇，覆盖 " + "、".join(domains[k]["label"] for k in covered) + "，全部由脚本按领域关键词抓取并打分排序。",
        "分数只反映标题与摘要里的关键词命中（领域锚点 + 术语数 + 标题锚点），不评价方法质量、实验是否充分，也不判断是否和你的工作直接相关。",
        "每天北京时间 06:00 自动更新；人工精读过的期号会替换掉对应的自动条目，并在归档里标注「人工精读」。",
    ]
    return {
        "edition": {
            "date": date_str,
            "number": number,
            "title": "%d 月 %d 日 · 每日论文雷达" % (date.month, date.day),
            "subtitle": "脚本按四个领域抓取 arXiv 最新投稿并初筛，未做人工解读。",
            "kicker": "AUTO · 每日自动更新",
            "blurb": "点开任意一篇可以看到 arXiv 原文摘要、作者与分类；值得跟踪的条目，再补中文解读。",
            "overview": overview,
            "threads": threads,
            "stats": stats,
            "note": [
                "本期由 scripts/daily_update.py 在 GitHub Actions 里自动生成，没有任何人工挑选或改写。",
                "「匹配度」是关键词打分：领域锚点 24 分起，每命中一个领域词 +9，标题里出现 GNSS/TEC/ROTI 等锚点再 +12。它只用于排序。",
                "同一天重复运行会跳过已存在的期号；想重跑请加 --force。",
                "机器初筛不等于推荐。重要结论、数字和适用边界请回到 arXiv 原文核对。",
            ],
        },
        "papers": papers,
    }


def git(*args):
    cmd = ["git", "-C", str(ROOT)] + list(args)
    print("$ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd).returncode


def main():
    parser = argparse.ArgumentParser(description="Build one automatic edition for the paper radar.")
    parser.add_argument("--date", default="", help="edition date, default today (Beijing)")
    parser.add_argument("--per-domain", type=int, default=4, help="max papers per domain (default 4)")
    parser.add_argument("--days", type=int, default=21, help="look back N days of arXiv submissions")
    parser.add_argument("--max", type=int, default=100, help="max arXiv results per query")
    parser.add_argument("--min-score", type=int, default=45, help="minimum keyword score")
    parser.add_argument("--no-push", action="store_true", help="build locally, do not commit/push")
    parser.add_argument("--force", action="store_true", help="overwrite an existing edition file")
    args = parser.parse_args()

    date_str = args.date or beijing_today().isoformat()
    existing, numbers, known_ids = load_editions()
    if date_str in existing and not args.force:
        print("edition %s already exists, nothing to do" % date_str)
        return 0

    domains = load_domains()
    candidates = fetch_candidates(date_str, args.days, args.max, args.min_score)
    print("candidates:", len(candidates))
    picked = pick(candidates, args.per_domain, known_ids)
    if not picked:
        print("no new candidates, skip publishing")
        return 0

    papers = [make_paper(item) for item in picked]
    number = (max(numbers) if numbers else 0) + 1
    edition = make_edition(date_str, papers, domains, number)

    EDITIONS.mkdir(parents=True, exist_ok=True)
    target = EDITIONS / (date_str + ".json")
    with target.open("w", encoding="utf-8") as handle:
        json.dump(edition, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    print("wrote", target, "with", len(papers), "papers")

    if subprocess.run([sys.executable, str(BUILD)], cwd=str(ROOT)).returncode != 0:
        print("build failed", file=sys.stderr)
        return 1
    if args.no_push:
        print("skipped commit/push (--no-push)")
        return 0

    git("add", "-A")
    if git("diff", "--cached", "--quiet") == 0:
        print("nothing to commit")
        return 0
    git("commit", "-m", "Daily edition " + date_str + " (auto, " + str(len(papers)) + " papers)")
    return git("push", "origin", "HEAD")


if __name__ == "__main__":
    sys.exit(main())
