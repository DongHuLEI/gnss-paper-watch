#!/usr/bin/env python3
"""Build the GNSS / ionosphere paper radar static site.

Reads data/papers.json and writes:
  index.html
  daily/<date>/index.html
  archive/index.html
  papers/<slug>/index.html
"""

import html
import json
import math
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "papers.json"

DOMAIN_ORDER = ["gnss", "iono", "ml", "perception"]
DOMAIN_COLORS = {
    "gnss": "#5aa9ff",
    "iono": "#37e2c0",
    "ml": "#b79cff",
    "perception": "#ffb454",
}
DOMAIN_SHORT = {
    "gnss": "GNSS",
    "iono": "IONO",
    "ml": "ML",
    "perception": "PERCEPT",
}


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def text(value: str) -> str:
    return html.escape(value, quote=False)


def read_data():
    with DATA.open(encoding="utf-8") as handle:
        return json.load(handle)


def join_paragraphs(paragraphs, tag="p"):
    return "\n".join(f"<{tag}>{text(p)}</{tag}>" for p in paragraphs)


def cover_svg(domain: str, index: int) -> str:
    """Deterministic, domain-specific cover art. No external images needed."""
    color = DOMAIN_COLORS[domain]
    seed = index + 3
    parts = [
        '<svg viewBox="0 0 640 360" role="img" aria-hidden="true" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">',
        "<defs>",
        f'<linearGradient id="fade{index}" x1="0" y1="0" x2="1" y2="1">',
        f'<stop offset="0" stop-color="{color}" stop-opacity=".95"/>',
        f'<stop offset="1" stop-color="{color}" stop-opacity=".08"/>',
        "</linearGradient>",
        f'<radialGradient id="glow{index}" cx=".25" cy=".2" r=".8">',
        f'<stop offset="0" stop-color="{color}" stop-opacity=".30"/>',
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/>',
        "</radialGradient>",
        "</defs>",
        f'<rect width="640" height="360" fill="url(#glow{index})"/>',
    ]

    # faint engineering grid
    for x in range(40, 640, 60):
        parts.append(f'<path d="M{x} 0V360" stroke="{color}" stroke-opacity=".07" stroke-width="1"/>')
    for y in range(30, 360, 45):
        parts.append(f'<path d="M0 {y}H640" stroke="{color}" stroke-opacity=".07" stroke-width="1"/>')

    if domain == "gnss":
        parts.append(f'<circle cx="330" cy="560" r="290" fill="none" stroke="{color}" stroke-opacity=".35" stroke-width="1.4"/>')
        parts.append(f'<circle cx="330" cy="560" r="360" fill="none" stroke="{color}" stroke-opacity=".14" stroke-width="1"/>')
        angle = (index * 13) % 37 - 18
        parts.append(f'<g transform="rotate({angle} 320 190)">')
        for orbit in range(3):
            rx = 205 + orbit * 72 + (index % 3) * 9
            ry = 72 + orbit * 27
            rot = -18 + orbit * 11
            parts.append(
                f'<ellipse cx="320" cy="190" rx="{rx}" ry="{ry}" transform="rotate({rot} 320 190)" '
                f'fill="none" stroke="{color}" stroke-opacity="{0.34 - orbit * 0.07}" stroke-width="1.2" stroke-dasharray="3 7"/>'
            )
        offsets = [(0, 0), (13, -9), (-17, 11), (8, 16), (21, 4)]
        sat_positions = [(150, 140), (470, 120), (390, 250), (215, 268), (510, 220)]
        for k, (sx, sy) in enumerate(sat_positions):
            sx += offsets[(k + index) % len(offsets)][0]
            sy += offsets[(k + index) % len(offsets)][1]
            parts.append(f'<path d="M{sx} {sy}L330 318" stroke="{color}" stroke-opacity=".18" stroke-width="1"/>')
            parts.append(f'<circle cx="{sx}" cy="{sy}" r="{4 + (k % 2)}" fill="{color}" fill-opacity=".9"/>')
            parts.append(f'<circle cx="{sx}" cy="{sy}" r="{10 + (k % 3) * 3}" fill="{color}" fill-opacity=".08"/>')
        parts.append('</g>')
        parts.append(f'<path d="M330 318l-14 20h28z" fill="{color}" fill-opacity=".8"/>')
        parts.append(f'<circle cx="330" cy="318" r="3.5" fill="#fff" fill-opacity=".9"/>')

    elif domain == "iono":
        for layer in range(5):
            amp = 16 + layer * 7
            base = 120 + layer * 34
            phase = seed * 0.4 + layer * 0.55
            pts = []
            for x in range(0, 660, 12):
                y = base + amp * math.sin(x / 58.0 + phase) + 5 * math.sin(x / 17.0 + layer)
                pts.append(f"{x},{y:.1f}")
            parts.append(
                f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
                f'stroke-opacity="{0.58 - layer * 0.085}" stroke-width="{2.0 - layer * 0.22}"/>'
            )
        for x in range(90, 590, 58):
            h = 75 + ((x * 13 + seed * 29) % 120)
            parts.append(
                f'<rect x="{x}" y="{330 - h}" width="10" height="{h}" fill="{color}" '
                f'fill-opacity="{0.06 + (x % 5) * 0.012}" stroke="{color}" stroke-opacity=".18"/>'
            )
        for k in range(7):
            x = 70 + (k * 83 + seed * 7) % 500
            y = 105 + (k * 47) % 180
            parts.append(f'<circle cx="{x}" cy="{y}" r="2.5" fill="{color}" fill-opacity=".9"/>')

    elif domain == "ml":
        nodes = []
        for k in range(16):
            x = 60 + (k * 97 + seed * 31) % 520
            y = 70 + (k * 53 + seed * 17) % 220
            nodes.append((x, y))
        for a in range(len(nodes)):
            for b in range(a + 1, len(nodes)):
                if (a * 7 + b * 11 + seed) % 13 == 0:
                    parts.append(
                        f'<path d="M{nodes[a][0]} {nodes[a][1]}L{nodes[b][0]} {nodes[b][1]}" '
                        f'stroke="{color}" stroke-opacity=".16" stroke-width="1"/>'
                    )
        for k, (x, y) in enumerate(nodes):
            r = 2.3 + (k % 4) * 0.8
            parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" fill-opacity="{0.55 + (k % 3) * 0.14}"/>')
            if k % 5 == 0:
                parts.append(f'<circle cx="{x}" cy="{y}" r="{r + 6}" fill="none" stroke="{color}" stroke-opacity=".28"/>')
        # highlighted path
        path = [nodes[i] for i in (2, 6, 9, 13)]
        d = "M" + "L".join(f"{x} {y}" for x, y in path)
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-opacity=".9" stroke-width="2.2"/>')
        for x, y in path:
            parts.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{color}"/>')

    else:  # perception
        for k in range(34):
            x = 34 + k * 17
            h = 14 + ((k * 37 + seed * 19) % 120)
            parts.append(
                f'<rect x="{x}" y="{320 - h}" width="8" height="{h}" fill="{color}" '
                f'fill-opacity="{0.10 + (k % 6) * 0.025}" stroke="{color}" stroke-opacity=".22"/>'
            )
        pts = []
        for x in range(0, 660, 10):
            y = 190 + 48 * math.sin(x / 31.0 + seed) * math.exp(-((x - 320) / 260) ** 2)
            pts.append(f"{x},{y:.1f}")
        parts.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-opacity=".8" stroke-width="2.4"/>')
        for r in (70, 112, 154):
            parts.append(f'<circle cx="320" cy="190" r="{r}" fill="none" stroke="{color}" stroke-opacity=".16" stroke-dasharray="4 8"/>')
        parts.append(f'<circle cx="320" cy="190" r="5" fill="{color}"/>')

    parts.append("</svg>")
    return "".join(parts)


def header(root: str, active: str = "") -> str:
    today_href = f"{root}daily/2026-10-20/index.html"
    if active == "today":
        today_href = "index.html" if root == "" else f"{root}daily/2026-10-20/index.html"
    return f"""<a class="skip-link" href="#content">跳到内容</a>
<header class="top"><div class="wrap nav"><strong><a href="{root}index.html">GNSS Paper Radar</a></strong><nav class="nav-links"><a href="{today_href}">今日</a><a href="{root}index.html#domains">领域</a><a href="{root}index.html#papers">论文</a><a href="{root}archive/index.html">归档</a><a href="{root}index.html#about">关于</a><span class="lang-toggle" role="group" aria-label="语言切换"><button type="button" data-set-lang="zh" aria-pressed="true">中文</button><button type="button" data-set-lang="en" aria-pressed="false">English</button></span></nav></div></header>"""


def footer() -> str:
    return """<footer>GNSS Paper Radar · 静态站点 · 人工精选 / 可脚本更新 · 数据来自 arXiv 摘要与公开论文页</footer>"""


def html_document(title: str, description: str, root: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN" data-lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{esc(description)}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta name="theme-color" content="#070b10">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' fill='%23070b10'/%3E%3Ccircle cx='32' cy='32' r='18' fill='none' stroke='%2337e2c0' stroke-width='3'/%3E%3Ccircle cx='32' cy='32' r='4' fill='%2337e2c0'/%3E%3C/svg%3E">
  <title>{esc(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap">
  <link rel="stylesheet" href="{root}assets/app.css">
</head>
<body>
{body}
<script src="{root}assets/app.js"></script>
</body>
</html>
"""


def domain_pill(domain: str, domains) -> str:
    return f'<span class="domain-pill" data-domain="{domain}">{esc(domains[domain]["label"])}</span>'


def paper_card(paper, index: int, domains, root: str) -> str:
    domain = paper["domain"]
    search_blob = " ".join(
        [
            paper["title_zh"],
            paper["title_en"],
            paper["one_liner"],
            paper["one_liner_en"],
            paper["id"],
            domains[domain]["label"],
            domains[domain]["en"],
            " ".join(paper["tags"]),
            " ".join(paper["authors"]),
        ]
    )
    tags = "".join(f'<span class="tag">{text(tag)}</span>' for tag in paper["tags"])
    return f"""<article class="card" data-domain="{domain}" data-paper-card data-search="{esc(search_blob)}">
  <a class="paper-cover cover-{domain}" href="{root}papers/{paper["slug"]}/index.html" aria-label="{esc(paper["title_zh"])}">
    {cover_svg(domain, index)}
    <span class="cover-label">{DOMAIN_SHORT[domain]}</span>
    <span class="cover-id">arXiv:{esc(paper["id"])}</span>
    <span class="cover-index">{index + 1:02d}</span>
  </a>
  <h3><a href="{root}papers/{paper["slug"]}/index.html"><span class="lang lang-zh lang-inline" data-lang="zh">{text(paper["title_zh"])}</span><span class="lang lang-en lang-inline" data-lang="en">{text(paper["title_en"])}</span></a></h3>
  <div class="meta">{esc(paper["date"])} · 匹配度 {paper["score"]} · {text(paper["tier"])} · {text(domains[domain]["label"])} · {esc(", ".join(paper["cats"]))}</div>
  {domain_pill(domain, domains)}
  <p class="insight"><span class="lang lang-zh lang-inline" data-lang="zh"><strong>一句话：</strong>{text(paper["one_liner"])}</span><span class="lang lang-en lang-inline" data-lang="en">{text(paper["one_liner_en"])}</span></p>
  <div class="tags">{tags}</div>
  <div class="links"><a href="https://arxiv.org/abs/{paper["id"]}">abs</a><a href="https://arxiv.org/pdf/{paper["id"]}">PDF</a><a href="{root}papers/{paper["slug"]}/index.html">方法拆解</a></div>
</article>"""


def build_home(data, root: str, active: str) -> str:
    edition = data["edition"]
    domains = data["domains"]
    papers = data["papers"]

    stats = "".join(
        f'<span class="stat"><b>{esc(item["value"])}</b><span>{text(item["label"])}</span></span>'
        for item in edition["stats"]
    )
    overview = "".join(f"<p>{text(p)}</p>" for p in edition["overview"])
    threads = "".join(
        f'<li data-domain="{item["domain"]}"><strong>{text(item["title"])}</strong>{text(item["text"])}</li>'
        for item in edition["threads"]
    )
    domain_cards = "".join(
        f"""<a class="domain-card" href="{root}topics/{key}/index.html" data-domain="{key}">
  <span class="domain-pill" data-domain="{key}">{esc(domains[key]["en"])}</span>
  <strong>{text(domains[key]["label"])}</strong>
  <em>{sum(1 for p in papers if p["domain"] == key)} 篇 · 进入领域页 →</em>
  <span>{text(domains[key]["desc"])}</span>
</a>"""
        for key in DOMAIN_ORDER
    )

    filter_buttons = [("all", "全部", len(papers))]
    filter_buttons += [(key, domains[key]["label"], sum(1 for p in papers if p["domain"] == key)) for key in DOMAIN_ORDER]
    filters = "".join(
        f'<button class="filter-btn" type="button" data-filter="{key}" aria-pressed="{"true" if key == "all" else "false"}">{text(label)} <span class="meta">{count}</span></button>'
        for key, label, count in filter_buttons
    )

    cards = "\n".join(paper_card(p, i, domains, root) for i, p in enumerate(papers))
    notes = "".join(f"<li>{text(n)}</li>" for n in edition["note"])

    today_link = f"{root}daily/{edition['date']}/index.html"
    body = f"""{header(root, active)}
<main class="wrap" id="content">
  <section class="hero">
    <div class="hero-copy">
      <div class="eyebrow"><span class="seal">第 {esc(edition["number"])} 期</span><b>{esc(edition["date"])}</b><span>{esc(edition["kicker"])}</span></div>
      <h1>{text(edition["title"])}</h1>
      <p class="muted">{text(edition["subtitle"])}</p>
      <p class="muted">{text(edition["blurb"])}</p>
      <div class="links"><a class="btn" href="{today_link}">本期固定页</a><a class="btn" href="{root}archive/index.html">查看归档</a><a class="btn" href="#papers">直接看论文</a></div>
    </div>
    <div class="stats">{stats}</div>
  </section>

  <section class="section" id="domains">
    <div class="editorial">
      <div>
        <h2>本期判断</h2>
        {overview}
      </div>
      <div>
        <ul class="threads">{threads}</ul>
      </div>
    </div>
    <div class="domain-index">{domain_cards}</div>
  </section>

  <section class="section" id="papers">
    <div class="section-head"><h2>本期论文 · {len(papers)} 篇</h2><p class="muted">按领域筛选，或搜索标题、作者、标签、arXiv ID。快捷键 <code>/</code> 聚焦搜索框。</p></div>
    <div class="filter-bar">
      <div class="filter-group">{filters}</div>
      <div class="search-wrap"><label for="paper-search">SEARCH</label><input id="paper-search" type="search" placeholder="ROTI / PPP / graph / 作者…" autocomplete="off" data-paper-search><span class="result-count" data-result-count>{len(papers)} / {len(papers)} 篇</span></div>
    </div>
    <div class="grid" data-paper-grid>
{cards}
      <div class="empty-state" data-empty-state>没有匹配的论文。换一个关键词，或切回「全部」。</div>
    </div>
  </section>

  <section class="section" id="about">
    <div class="section-head"><h2>编选说明</h2><p class="muted">这份站点如何选论文，以及它不做什么。</p></div>
    <ul class="brief">{notes}</ul>
    <div class="method-note">
      <div><strong>领域相关性 40%</strong><span>是否落在 GNSS 定位、电离层监测、深度学习预测、工程感知四条主线内。</span></div>
      <div><strong>方法增量 25%</strong><span>是否改变问题建模、标签定义、数据使用或工程约束，而不是只换网络/换指标。</span></div>
      <div><strong>证据强度 20%</strong><span>实测/仿真、事件数、站点数、是否留出验证、是否有代码或数据。</span></div>
      <div><strong>连接度 15%</strong><span>与 ROTI–PPP、CDSF-NET、DORIS/ISMR、CORS 完好性等既有工作的可迁移程度。</span></div>
    </div>
    <div class="about-grid" style="margin-top:16px">
      <div class="brief"><h2>与你知识库的对应</h2><p>站点里的「与你工作的连接」不是泛泛的启发，而是尽量指向你已有的数据与问题：ROTI 与 PPP 恢复时序、短弧/连续弧龄、CDSF-NET 的条件物理融合、DORIS-ROTI 的互补观测、ISMR 高频闪烁、CORS 网络一致性。</p></div>
      <div class="brief"><h2>更新方式</h2><p>当前页面由 <code>scripts/build_site.py</code> 从 <code>data/papers.json</code> 生成；<code>scripts/fetch_arxiv.py</code> 可抓取每日候选并按关键词打分。中文解读需要人工确认后再写入数据文件，避免把自动摘要当成事实。</p></div>
    </div>
  </section>
</main>
{footer()}"""
    return html_document(
        f"{edition['title']} · {edition['date']}",
        edition["subtitle"],
        root,
        body,
    )


def build_archive(data) -> str:
    edition = data["edition"]
    domains = data["domains"]
    counts = " · ".join(f"{domains[d]['label']} {sum(1 for p in data['papers'] if p['domain'] == d)}" for d in DOMAIN_ORDER)
    body = f"""{header("../")}
<main class="wrap" id="content">
  <section class="hero"><div><div class="eyebrow"><span class="seal">ARCHIVE</span></div><h1>归档</h1><p class="muted">按日期查看已生成的期号。当前只有创刊号；后续可用同一生成器追加。</p></div></section>
  <section class="section">
    <ul class="archive">
      <li><a href="../daily/{edition['date']}/index.html"><strong>{edition['date']} · 第 {edition['number']} 期</strong></a><div class="meta">{len(data['papers'])} 篇论文 · {counts}</div><p class="muted">{text(edition['title'])}</p></li>
    </ul>
  </section>
</main>
{footer()}"""
    return html_document("归档 · GNSS Paper Radar", "GNSS 定位与电离层论文雷达归档", "../", body)


def build_topic(key, data) -> str:
    domain = data["domains"][key]
    indexed = [(i, paper) for i, paper in enumerate(data["papers"]) if paper["domain"] == key]
    cards = "\n".join(paper_card(paper, index, data["domains"], "../../") for index, paper in indexed)
    body = f"""{header("../../")}
<main class="wrap" id="content">
  <section class="hero">
    <div>
      <div class="eyebrow"><span class="seal">FIELD · {esc(domain['en'])}</span><span>{len(indexed)} 篇</span></div>
      <h1>{text(domain['label'])}</h1>
      <p class="muted">{text(domain['desc'])}</p>
      <p class="muted">{text(domain['long'])}</p>
      <div class="links"><a class="btn" href="../../index.html#papers">全部论文</a><a class="btn" href="../../archive/index.html">归档</a></div>
    </div>
    <div class="domain-card" data-domain="{key}" style="align-self:stretch;justify-content:center">
      <span class="domain-pill" data-domain="{key}">{esc(domain['en'])}</span>
      <strong>{text(domain['label'])}</strong>
      <em>{len(indexed)} 篇 · 本期</em>
      <span>按匹配度与证据强度排序；单篇页给出方法拆解、关键数字和适用边界。</span>
    </div>
  </section>
  <section class="section">
    <div class="section-head"><h2>{text(domain['label'])} · 本期论文</h2><p class="muted">返回首页可按关键词搜索全部 16 篇。</p></div>
    <div class="grid">{cards}</div>
  </section>
</main>
{footer()}"""
    return html_document(f"{domain['label']} · GNSS Paper Radar", domain["desc"], "../../", body)


def build_paper(paper, data, index: int) -> str:
    domains = data["domains"]
    domain = paper["domain"]
    tags = "".join(f'<span class="tag">{text(tag)}</span>' for tag in paper["tags"])
    metrics = "".join(
        f'<div class="poster-metric"><strong class="poster-metric-value">{text(m["value"])}</strong>'
        f'<span class="poster-metric-label"><span class="lang lang-zh lang-inline" data-lang="zh">{text(m["label"])}</span>'
        f'<span class="lang lang-en lang-inline" data-lang="en">{text(m.get("label_en", m["label"]))}</span></span></div>'
        for m in paper["metrics"]
    )
    essence = "".join(
        f'<div class="poster-method-essence-item"><h3>{text(item["h"])}</h3><p>{text(item["p"])}</p></div>'
        for item in paper["essence"]
    )
    problem = join_paragraphs(paper["problem"])
    method = join_paragraphs(paper["method"])
    results = join_paragraphs(paper["results"])
    limits = join_paragraphs(paper["limits"])
    relevance = join_paragraphs(paper["relevance"])
    authors = ", ".join(paper["authors"])
    code_link = ""
    if paper["links"].get("code"):
        code_link = f'<li><a href="{esc(paper["links"]["code"])}">官方代码 / Code</a></li>'
    sources = [
        f'<li><a href="{esc(paper["links"]["abs"])}">arXiv 摘要页</a></li>',
        f'<li><a href="{esc(paper["links"]["pdf"])}">arXiv PDF</a></li>',
        code_link,
    ]
    sources_html = "".join(s for s in sources if s)

    body = f"""{header("../../")}
<main class="wrap" id="content">
<article class="poster-shell">
  <header class="poster-cover">
    <div class="poster-back"><a href="../../daily/{data['edition']['date']}/index.html">← 本期论文合集</a><span class="meta">第 {data['edition']['number']} 期 · {esc(data['edition']['date'])}</span></div>
    <div class="poster-kicker">{text(domains[domain]['label'])} · {text(paper['date'])} · {text(paper['tier'])} · 匹配度 {paper['score']}</div>
    <h1><span class="lang lang-zh lang-inline" data-lang="zh">{text(paper['title_zh'])}</span><span class="lang lang-en lang-inline" data-lang="en">{text(paper['title_en'])}</span></h1>
    <p class="poster-title-en">{text(paper['title_en'])}</p>
    <p class="poster-authors">{text(authors)}</p>
    <p class="poster-lead"><span class="lang lang-zh lang-block" data-lang="zh">{text(paper['lead_zh'])}</span><span class="lang lang-en lang-block" data-lang="en">{text(paper['lead_en'])}</span></p>
    <div class="poster-meta"><span>{esc(paper['date'])}</span><span>{esc(paper['id'])}</span><span>{esc(', '.join(paper['cats']))}</span><span>{text(domains[domain]['label'])}</span><a href="{esc(paper['links']['abs'])}">原文 / Paper</a></div>
    <div class="tags">{tags}</div>
  </header>

  <nav class="poster-nav" aria-label="海报章节导航"><a href="#poster-01"><span class="nav-no">01</span>结论与问题</a><a href="#poster-02"><span class="nav-no">02</span>方法</a><a href="#poster-03"><span class="nav-no">03</span>结果</a><a href="#poster-04"><span class="nav-no">04</span>边界与启发</a></nav>

  <div class="poster-metrics" aria-label="关键指标">{metrics}</div>

  <section class="poster-context">
    <p class="poster-context-label">阅读定位 · Why read it</p>
    <div class="poster-context-grid">
      <div class="poster-context-card"><h3>它解决什么</h3><p>{text(paper['problem'][0])}</p></div>
      <div class="poster-context-card"><h3>方法关键词</h3><div class="tags">{tags}</div></div>
      <div class="poster-context-card"><h3>证据类型</h3><p>{text(paper['results'][0])}</p></div>
    </div>
  </section>

  <section class="poster-method-essence">
    <p class="poster-method-essence-label">方法本质拆解 · What actually changed</p>
    <div class="poster-method-essence-grid">{essence}</div>
    <p class="poster-method-essence-note">{text(paper['one_liner'])}</p>
  </section>

  <section class="poster-section" id="poster-01">
    <div class="poster-section-head"><span class="poster-section-no">01</span><h2 class="poster-section-title">结论与问题<span class="poster-section-en">Conclusion &amp; Motivation</span></h2></div>
    <div class="poster-section-body"><h3>核心结论</h3><p>{text(paper['one_liner'])}</p><p>{text(paper['lead_zh'])}</p><h3>研究问题</h3>{problem}</div>
  </section>

  <section class="poster-section" id="poster-02">
    <div class="poster-section-head"><span class="poster-section-no">02</span><h2 class="poster-section-title">方法<span class="poster-section-en">Method</span></h2></div>
    <div class="poster-section-body"><h3>方法总览</h3>{method}<h3>实现层面的关键变化</h3><p>{text(paper['essence'][2]['p'])}</p></div>
  </section>

  <section class="poster-section" id="poster-03">
    <div class="poster-section-head"><span class="poster-section-no">03</span><h2 class="poster-section-title">结果<span class="poster-section-en">Results</span></h2></div>
    <div class="poster-section-body"><h3>主要结果</h3>{results}</div>
  </section>

  <section class="poster-section" id="poster-04">
    <div class="poster-section-head"><span class="poster-section-no">04</span><h2 class="poster-section-title">边界与启发<span class="poster-section-en">Limits &amp; Transfer</span></h2></div>
    <div class="poster-section-body"><h3>局限与待核验</h3>{limits}<div class="relevance-box"><h3>与你研究路线的关系</h3>{relevance}</div><p class="meta">以上中文解读基于 arXiv 摘要与论文公开信息；未在摘要中出现的数字不作补写。需要精确实验设置时请回到原文。</p></div>
  </section>

  <section class="poster-abstract">
    <h2>中文摘要速读 · Summary</h2>
    <p>{text(paper['lead_zh'])}</p>
    <h2 style="margin-top:20px">原文摘要 · Abstract</h2>
    <p>{text(paper['abstract_en'])}</p>
  </section>

  <div class="poster-sources">证据来源：<ul>{sources_html}</ul></div>
</article>
</main>
{footer()}"""
    return html_document(
        f"{paper['title_zh']} · GNSS Paper Radar",
        paper["one_liner"],
        "../../",
        body,
    )


def validate(data):
    required = [
        "id", "slug", "domain", "date", "score", "tier", "title_zh", "title_en",
        "authors", "cats", "tags", "one_liner", "one_liner_en", "lead_zh", "lead_en",
        "metrics", "problem", "method", "essence", "results", "limits", "relevance",
        "abstract_en", "links",
    ]
    errors = []
    seen_ids = set()
    seen_slugs = set()
    for paper in data.get("papers", []):
        for key in required:
            if key not in paper or paper[key] in ("", [], None):
                errors.append("%s: missing %s" % (paper.get("id", "?"), key))
        if paper.get("domain") not in data.get("domains", {}):
            errors.append("%s: unknown domain %s" % (paper.get("id", "?"), paper.get("domain")))
        if len(paper.get("essence", [])) != 4:
            errors.append("%s: essence needs exactly 4 items" % paper.get("id", "?"))
        if paper.get("id") in seen_ids:
            errors.append("%s: duplicate id" % paper.get("id"))
        if paper.get("slug") in seen_slugs:
            errors.append("%s: duplicate slug" % paper.get("slug"))
        seen_ids.add(paper.get("id"))
        seen_slugs.add(paper.get("slug"))
    if errors:
        raise SystemExit("data validation failed:\n  " + "\n  ".join(errors))


def main() -> None:
    data = read_data()
    validate(data)
    edition = data["edition"]
    date = edition["date"]

    # home (latest) and dated copy
    (ROOT / "index.html").write_text(build_home(data, "", "today"), encoding="utf-8")
    daily_dir = ROOT / "daily" / date
    daily_dir.mkdir(parents=True, exist_ok=True)
    (daily_dir / "index.html").write_text(build_home(data, "../../", "today"), encoding="utf-8")

    # archive
    archive_dir = ROOT / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "index.html").write_text(build_archive(data), encoding="utf-8")

    # paper pages
    papers_dir = ROOT / "papers"
    if papers_dir.exists():
        shutil.rmtree(papers_dir)
    papers_dir.mkdir(parents=True)
    for index, paper in enumerate(data["papers"]):
        target = papers_dir / paper["slug"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(build_paper(paper, data, index), encoding="utf-8")

    # domain landing pages
    topics_dir = ROOT / "topics"
    if topics_dir.exists():
        shutil.rmtree(topics_dir)
    topics_dir.mkdir(parents=True)
    for key in DOMAIN_ORDER:
        target = topics_dir / key
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(build_topic(key, data), encoding="utf-8")

    # tiny 404
    not_found = html_document(
        "页面不存在 · GNSS Paper Radar",
        "页面不存在",
        "",
        f"""{header("")}<main class="wrap" id="content"><section class="hero"><div><div class="eyebrow"><span class="seal">404</span></div><h1>页面不存在</h1><p class="muted">链接可能已经移动。回到首页或归档继续浏览。</p><div class="links"><a class="btn" href="index.html">回到首页</a><a class="btn" href="archive/index.html">归档</a></div></div></section></main>{footer()}""",
    )
    (ROOT / "404.html").write_text(not_found, encoding="utf-8")

    print(f"built {len(data['papers'])} papers for {date}")


if __name__ == "__main__":
    main()
