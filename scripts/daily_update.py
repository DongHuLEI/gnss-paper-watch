#!/usr/bin/env python3
"""Retrieve, optionally interpret, archive and publish the daily research radar."""

import argparse
import datetime as dt
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from deepseek_client import DeepSeekClient, normalize
from fetch_arxiv import ARXIV_ID, collect_candidates, fetch_by_ids
from radar_config import (
    DATA, ROOT, beijing_now, classify, known_ids, load_config, load_editions,
    load_json, utc_timestamp, write_json,
)

SEARCH_TERMS = {
    "gnss": "GNSS PPP RTK ambiguity resolution",
    "iono": "ionosphere TEC ROTI scintillation",
    "ml": '"time series" "foundation model" forecasting',
    "perception": '"sensor fusion" SLAM GNSS localization',
    "embodied": '"vision-language-action" robot learning',
    "training": 'LoRA post-training distillation "data curation"',
}


def short(value, limit=180):
    value = normalize(value)
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"


def pick(candidates, domains, per_domain, maximum, existing=None):
    selected = list(existing or [])
    selected_ids = {item["id"] for item in selected}
    for turn in range(per_domain):
        for domain in domains:
            if len(selected) >= maximum:
                return selected
            count = sum(paper["domain"] == domain for paper in selected)
            if count > turn:
                continue
            pool = [item for item in candidates if item["domain"] == domain and item["id"] not in selected_ids]
            pool.sort(key=lambda item: item["date"], reverse=True)
            pool.sort(key=lambda item: -item["score"])
            if pool:
                selected.append(pool[0])
                selected_ids.add(pool[0]["id"])
    return selected


def make_paper(item):
    return {
        "id": item["id"], "slug": "arxiv-" + item["id"].replace("/", "-"),
        "domain": item["domain"], "domains": item.get("domains", [item["domain"]]),
        "lenses": item.get("lenses", []), "date": item["date"], "updated": item.get("updated", item["date"]),
        "score": item["score"], "domain_scores": item.get("domain_scores", {}),
        "tier": "检索初筛", "auto": True, "reading_status": "metadata",
        "title_zh": item["title"], "title_en": item["title"],
        "authors": item.get("authors", []), "cats": item.get("cats", []),
        "tags": item.get("matched_terms", [])[:5],
        "one_liner": short(item["abstract"]), "one_liner_en": short(item["abstract"]),
        "lead_zh": "自动检索条目，尚未生成中文解读。以下为 arXiv 原始摘要；初筛分数不代表论文质量。",
        "lead_en": "Retrieved from arXiv. No AI interpretation is available yet; metadata and abstract are from the source.",
        "abstract_en": item["abstract"], "version": item.get("version", ""),
        "links": {"abs": item["abs_url"], "pdf": item["pdf_url"]},
        "retrieved_at": utc_timestamp(),
    }


def arxiv_id_from_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.hostname not in ("arxiv.org", "www.arxiv.org", "export.arxiv.org"):
        return None
    path = urllib.parse.unquote(parsed.path)
    match = re.match(r"^/(?:abs|html|pdf)/(.+?)(?:\.pdf)?/?$", path)
    if not match or not ARXIV_ID.match(match.group(1)):
        return None
    return re.sub(r"v\d+$", "", match.group(1))


def supplement(client, domains, lenses, known, as_of, days, min_score):
    pages = []
    for domain in domains:
        query = SEARCH_TERMS.get(domain, domains[domain]["en"])
        query += " site:arxiv.org after:" + (as_of - dt.timedelta(days=days)).isoformat()
        pages.extend(client.search(query))
    ids = sorted({value for page in pages for value in [arxiv_id_from_url(page["url"])] if value and value not in known})
    candidates = []
    status = "not_needed"
    if ids:
        try:
            time.sleep(3.1)
            for item in fetch_by_ids(ids):
                published = dt.datetime.strptime(item["date"], "%Y-%m-%d").date()
                if item["id"] in known or not as_of - dt.timedelta(days=days) <= published <= as_of:
                    continue
                result = classify(item["title"], item["abstract"], domains, lenses)
                if result["score"] >= min_score:
                    item.update(result)
                    candidates.append(item)
            status = "ok"
        except Exception as exc:
            status = "metadata_verification_failed_" + type(exc).__name__
    return candidates, pages, status


def enrich(papers, client, profile, pages):
    for paper in papers:
        if not paper.get("auto") or paper.get("analysis"):
            continue
        if not client.available:
            paper["analysis_status"] = client.state
            continue
        extras = []
        for page in pages:
            if arxiv_id_from_url(page["url"]) == paper["id"] and page.get("text"):
                extras.append(page)
                break
        if not extras and client.ledger["successes"]["chat"] < client.config["daily_paper_limit"]:
            url = "https://arxiv.org/html/" + paper["id"] + paper.get("version", "")
            page = client.fetch(url)
            if page and normalize(paper["title_en"]).lower() in normalize(page["text"]).lower():
                extras.append(page)
        result, status = client.analyze(paper, profile, extras)
        paper["analysis_status"] = status
        if result:
            paper["analysis"] = result["analysis"]
            paper["ai"] = result["provenance"]
            paper["reading_status"] = "ai"
            paper["tier"] = "AI 解读 · 待核验"
            paper["title_zh"] = result["analysis"]["title_zh"]
            paper["lead_zh"] = result["analysis"]["summary"]
            paper["one_liner"] = short(result["analysis"]["summary"])
            paper["tags"] = result["analysis"]["tags"][:5]


def make_edition(date_str, papers, domains, number, retrieval, client, pages):
    ai_count = sum(bool(paper.get("analysis")) for paper in papers)
    covered = [key for key in domains if any(paper["domain"] == key for paper in papers)]
    threads = []
    for domain in covered:
        pool = [paper for paper in papers if paper["domain"] == domain]
        best = max(pool, key=lambda paper: paper["score"])
        threads.append({
            "domain": domain, "title": "%s · %d 篇" % (domains[domain]["label"], len(pool)),
            "text": short(best["title_zh"], 100),
        })
    return {
        "edition": {
            "date": date_str, "number": number, "title": date_str + " · 研究日报",
            "subtitle": "GNSS 与电离层为主线，连接科学 AI、具身智能和模型训练。",
            "kicker": "DAILY RESEARCH", "blurb": "本期 %d 篇，%d 篇 AI 中文解读；所有条目保留原始来源。" % (len(papers), ai_count),
            "overview": [
                "本期收录 %d 篇，覆盖 %s。" % (len(papers), "、".join(domains[key]["label"] for key in covered) or "暂无新增领域"),
                "AI 解读来自可核验的摘要或网页摘录，不等于人工审稿或全文精读；证据引用与迁移建议分开显示。",
                "初筛分数只用于领域排序，不评价论文质量。没有新稿的领域不会用无关论文凑数。",
            ],
            "threads": threads,
            "stats": [{"value": str(len(papers)), "label": "本期论文"}, {"value": str(ai_count), "label": "AI 解读"},
                      {"value": str(len(covered)), "label": "覆盖领域"}, {"value": "6", "label": "研究方向"}],
            "note": ["来源为 arXiv 元数据及标注过的公开网页，未向模型发送飞书原文或私有数据。",
                     "AI 提炼的事实要求有来源；自动校验不能替代人工核验。",
                     "每日提前触发并安排补跑；GitHub Actions 可能延迟，站点会显示实际检查时间。"],
            "generated_at": utc_timestamp(), "retrieval_status": retrieval["status"], "ai_status": client.state,
        },
        "papers": papers,
        "discovery": [{key: page.get(key) for key in ("title", "url", "date", "snippet")} for page in pages],
    }


def publish(date_str):
    paths = ["index.html", "404.html", "daily", "archive", "papers", "topics", "library", "learn", "about",
             "data/editions", "data/status.json", "data/usage", "data/deep_reads", "data/reading_queue.json", "assets/deep-reading"]
    paths = [path for path in paths if (ROOT / path).exists()]
    subprocess.check_call(["git", "add", "-A", "--"] + paths, cwd=str(ROOT))
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(ROOT)).returncode == 0:
        return
    subprocess.check_call(["git", "commit", "-m", "Research radar update " + date_str], cwd=str(ROOT))
    subprocess.check_call(["git", "push", "origin", "HEAD"], cwd=str(ROOT))


def main():
    domains, lenses, settings = load_config()
    config = settings["retrieval"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="")
    parser.add_argument("--per-domain", type=int, default=config["papers_per_domain"])
    parser.add_argument("--days", type=int, default=config["days"])
    parser.add_argument("--max", type=int, default=config["results_per_domain"])
    parser.add_argument("--min-score", type=int, default=config["min_score"])
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--no-build", action="store_true", help="prepare data only")
    parser.add_argument("--force", action="store_true", help="refresh an automatic issue; never replace reviewed entries")
    parser.add_argument("--skip-ai", action="store_true")
    parser.add_argument("--require-ai", action="store_true", help="fail instead of metadata fallback when no AI is available")
    parser.add_argument("--candidates", default="", help="reuse a verified retrieval file from the same day")
    parser.add_argument("--show-status", action="store_true", help="print public status without running an update")
    args = parser.parse_args()
    if args.show_status:
        status = load_json(DATA / "status.json") if (DATA / "status.json").exists() else {}
        ai = status.get("ai", {})
        print("## Research radar status\n")
        for label, value in (("Checked", status.get("checked_at", "not checked")),
                             ("Retrieval", status.get("retrieval_status", "unknown")),
                             ("Result", status.get("result", "unknown")),
                             ("AI", ai.get("state", "unknown")),
                             ("AI summaries", status.get("ai_summaries", 0)),
                             ("Reported tokens", ai.get("input_tokens", 0) + ai.get("output_tokens", 0))):
            print("- %s: %s" % (label, value))
        if settings["deepseek"].get("full_reading_enabled"):
            print("- Reading skill: paper-deep-reading")
            print("- Full readings pending: %s" % status.get("full_reading", {}).get("pending", "not run yet"))
        failed = [domains[item["domain"]]["label"] for item in status.get("queries", [])
                  if item.get("status") != "ok" and item.get("domain") in domains]
        if failed:
            print("- Incomplete sources: " + "、".join(failed))
        return 0
    from automation_gate import automation_status
    automation = automation_status(settings)
    if not automation["enabled"]:
        print("Daily automation paused: %s; historical readings %d/%d. No retrieval or AI calls started." % (
            automation["reason"], automation["completed"], automation["total"],
        ), flush=True)
        return 0
    if args.per_domain < 1 or args.days < 1 or not 1 <= args.max <= 200 or not 0 <= args.min_score <= 100:
        parser.error("invalid retrieval limits")
    if args.no_build and not args.no_push:
        parser.error("--no-build requires --no-push")
    as_of = dt.datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else beijing_now().date()
    date_str = as_of.isoformat()
    if as_of > beijing_now().date():
        parser.error("cannot publish a future edition")
    editions = load_editions()
    current = next((view for view in editions if view["edition"]["date"] == date_str), None)
    if current and any(not paper.get("auto") for paper in current["papers"]) and args.force:
        parser.error("refusing to overwrite reviewed entries")
    client_config = dict(settings["deepseek"])
    if args.skip_ai:
        client_config["enabled"] = False
    client = DeepSeekClient(client_config, beijing_now().date().isoformat())
    if args.require_ai and not client.available:
        print("AI unavailable: " + client.state, file=sys.stderr)
        return 2
    known = known_ids(editions)
    papers = list(current["papers"]) if current else []
    should_retrieve = not current or args.force or current["edition"].get("retrieval_status") in ("partial", "failed")
    retrieval = {"status": "already_checked", "queries": [], "candidates": []}
    pages = []
    supplement_status = "not_requested"
    if should_retrieve:
        if args.candidates:
            retrieval = load_json(Path(args.candidates))
            if retrieval.get("as_of") != date_str or retrieval.get("status") not in ("ok", "partial"):
                parser.error("candidate file must be a successful retrieval for the requested day")
        else:
            retrieval = collect_candidates(args.days, args.max, args.min_score, as_of, known)
        candidates = {item["id"]: item for item in retrieval["candidates"] if item["id"] not in known}
        if client.available:
            extra, pages, supplement_status = supplement(client, domains, lenses, known, as_of, args.days, args.min_score)
            candidates.update((item["id"], item) for item in extra)
        selected = pick(list(candidates.values()), domains, args.per_domain,
                        config["max_daily_papers"], existing=papers)
        papers = [item if "title_en" in item else make_paper(item) for item in selected]
    reading_status = {}
    excluded = automation["skipped"]
    if client.config.get("full_reading_enabled"):
        from reading_pipeline import enrich_full_readings
        reading_status = enrich_full_readings(papers, client, settings["research_profile"], editions,
                                              deadline=time.monotonic() + 18 * 60, excluded=excluded)
    else:
        enrich([paper for paper in papers if paper["id"] not in excluded], client, settings["research_profile"], pages)
    previous = load_json(DATA / "status.json") if (DATA / "status.json").exists() else {}
    if retrieval["status"] == "already_checked" and previous.get("checked_date") == date_str:
        query_records = previous.get("queries", [])
        candidate_count = previous.get("candidate_count", 0)
        retrieved_at = previous.get("retrieved_at")
        retrieval_state = previous.get("retrieval_status", "already_checked")
    else:
        query_records = retrieval["queries"]
        candidate_count = len(retrieval["candidates"])
        retrieved_at = utc_timestamp()
        retrieval_state = retrieval["status"]
    status = {
        "checked_at": utc_timestamp(), "checked_date": date_str, "retrieval_status": retrieval_state,
        "retrieved_at": retrieved_at, "queries": query_records, "candidate_count": candidate_count,
        "issue_date": date_str if papers else (editions[0]["edition"]["date"] if editions else None),
        "issue_papers": len(papers), "ai_summaries": sum(bool(paper.get("analysis")) for paper in papers),
        "full_readings": sum((DATA / "deep_reads" / (paper["id"] + ".json")).exists() for paper in papers),
        "ai": client.public_status(), "supplement_status": supplement_status, "full_reading": reading_status,
        "result": "retrieval_failed" if retrieval["status"] == "failed" else (
            ("already_checked" if not should_retrieve else "updated") if papers else "no_new_papers"
        ),
    }
    if papers:
        numbers = [int(view["edition"]["number"]) for view in editions]
        number = current["edition"]["number"] if current else max(numbers or [0]) + 1
        if not should_retrieve and current:
            issue = {key: value for key, value in current.items() if key != "_path"}
            issue["papers"] = papers
            issue["edition"]["ai_status"] = client.state
            issue["edition"]["blurb"] = "本期 %d 篇，%d 篇 AI 中文解读；所有条目保留原始来源。" % (len(papers), status["ai_summaries"])
        else:
            issue = make_edition(date_str, papers, domains, number, retrieval, client, pages)
            if current:
                discovery = list(current.get("discovery", []))
                issue["discovery"] = discovery + [page for page in issue["discovery"] if page not in discovery]
        if client.config.get("full_reading_enabled"):
            issue["edition"]["blurb"] = "本期 %d 篇，%d 篇图文全文导读、%d 篇既有摘要级解读；自动导读仍待核验。" % (len(papers), status["full_readings"], status["ai_summaries"])
            issue["edition"]["full_readings"] = status["full_readings"]
            issue["edition"]["reading_skill"] = "paper-deep-reading"
        write_json(DATA / "editions" / (date_str + ".json"), issue)
    write_json(DATA / "status.json", status)
    write_json(client.ledger_path, client.ledger)
    if not args.no_build:
        subprocess.check_call([sys.executable, str(ROOT / "scripts" / "build_site.py")], cwd=str(ROOT))
    if not args.no_push:
        publish(date_str)
    print("%s: %d papers, %d AI summaries; AI=%s; retrieval=%s" % (
        date_str, len(papers), status["ai_summaries"], client.state, retrieval["status"]), flush=True)
    if args.require_ai and not (status["ai_summaries"] or status["full_readings"]):
        return 2
    return 1 if retrieval["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
