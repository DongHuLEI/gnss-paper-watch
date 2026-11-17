#!/usr/bin/env python3
"""Build the research radar and an allowlisted deployment directory."""

import argparse
import calendar
import datetime as dt
import html
import json
import re
import shutil
import urllib.parse
from collections import Counter
from pathlib import Path

from radar_config import (
    BEIJING, DATA, ROOT, classify, load_config, load_editions, load_json,
)
from deep_reading import load_deep_reads, render as render_deep_read

STATUS_LABELS = {"metadata": "检索初筛", "ai": "AI 解读 · 待核验", "curated": "整理摘要", "deep": "图文精读 · 全文导读示范"}


def esc(value):
    return html.escape(str(value), quote=True)


def paragraphs(values):
    return "".join("<p>%s</p>" % esc(value) for value in values)


def bullet_list(values):
    return "<ul>" + "".join("<li>%s</li>" % esc(value) for value in values) + "</ul>"


def dual(zh, en):
    return '<span class="lang-zh">%s</span><span class="lang-en" lang="en">%s</span>' % (esc(zh), esc(en))


def safe_link(url):
    parsed = urllib.parse.urlsplit(str(url))
    return str(url) if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password else "#sources"


def timestamp(value):
    if not value:
        return "尚无检查记录"
    try:
        moment = dt.datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
        return moment.astimezone(BEIJING).strftime("%m-%d %H:%M") + " 北京时间"
    except ValueError:
        return str(value)


def validate(editions, domains):
    dates = set()
    for view in editions:
        meta = view.get("edition", {})
        date = meta.get("date", "")
        dt.datetime.strptime(date, "%Y-%m-%d")
        if date in dates or view["_path"].stem != date:
            raise ValueError("duplicate or mismatched edition date: " + date)
        dates.add(date)
        if not meta.get("title") or not str(meta.get("number", "")):
            raise ValueError("missing edition title/number: " + date)
        ids, slugs = set(), set()
        for paper in view.get("papers", []):
            for key in ("id", "slug", "title_en", "abstract_en", "domain", "date", "authors", "links"):
                if not paper.get(key):
                    raise ValueError("%s: missing %s" % (paper.get("id", "?"), key))
            if paper["domain"] not in domains or not re.match(r"^arxiv-[a-zA-Z0-9.-]+$", paper["slug"]):
                raise ValueError("invalid domain or slug: " + paper["id"])
            dt.datetime.strptime(paper["date"], "%Y-%m-%d")
            if paper["id"] in ids or paper["slug"] in slugs:
                raise ValueError("duplicate paper in " + date)
            ids.add(paper["id"])
            slugs.add(paper["slug"])


class Site:
    def __init__(self):
        self.domains, self.lenses, self.settings = load_config()
        self.editions = load_editions()
        if not self.editions:
            raise ValueError("no editions found")
        validate(self.editions, self.domains)
        self.latest = self.editions[0]
        self.status = load_json(DATA / "status.json") if (DATA / "status.json").exists() else {}
        self.catalogue = {}
        self.issues = {}
        self.deep_reads = load_deep_reads(DATA / "deep_reads")
        priority = {"deep": 4, "curated": 3, "ai": 2, "metadata": 1}
        for view in self.editions:
            rows = []
            for raw in view["papers"]:
                paper = self.prepare(raw, view["edition"])
                rows.append(paper)
                previous = self.catalogue.get(paper["id"])
                if previous:
                    paper["issues"] = sorted(set(previous["issues"] + paper["issues"]), reverse=True)
                    paper["collected"] = min(previous["collected"], paper["collected"])
                    if priority[previous["status"]] >= priority[paper["status"]]:
                        previous["issues"] = paper["issues"]
                        previous["collected"] = paper["collected"]
                        continue
                self.catalogue[paper["id"]] = paper
            self.issues[view["edition"]["date"]] = rows
        if set(self.deep_reads) - set(self.catalogue):
            raise ValueError("deep-reading overlay has no matching paper")
        self.papers = sorted(self.catalogue.values(), key=lambda paper: (paper["date"], paper["score"]), reverse=True)

    def prepare(self, raw, edition):
        paper = dict(raw)
        inferred = classify(paper["title_en"], paper["abstract_en"], self.domains, self.lenses)
        paper["domains"] = list(dict.fromkeys([paper["domain"]] + paper.get("domains", []) + inferred["domains"]))
        paper["domains"] = [key for key in paper["domains"] if key in self.domains]
        paper["lenses"] = list(dict.fromkeys(paper.get("lenses", []) + inferred["lenses"]))
        paper["lenses"] = [key for key in paper["lenses"] if key in self.lenses]
        paper["status"] = "ai" if paper.get("analysis") else ("metadata" if paper.get("auto") else "curated")
        paper["title_zh"] = paper.get("title_zh") or paper["title_en"]
        paper["tags"] = paper.get("tags") or inferred["matched_terms"][:5]
        paper["one_liner"] = paper.get("one_liner") or paper["abstract_en"][:220]
        paper["one_liner_en"] = paper.get("one_liner_en") or paper["abstract_en"][:220]
        paper["score"] = paper.get("score", inferred["score"])
        paper["issues"] = [edition["date"]]
        paper["collected"] = edition["date"]
        if paper["id"] in self.deep_reads:
            paper["deep_read"] = self.deep_reads[paper["id"]]
            paper["status"] = "deep"
            paper["title_zh"] = paper["deep_read"]["title_zh"]
            paper["one_liner"] = paper["deep_read"]["dek"]
            paper["tags"] = list(dict.fromkeys(["全文导读", "Flow Matching", "物理引导"] + paper["tags"]))
        return paper

    def count_domain(self, key, papers=None):
        return sum(key in paper["domains"] for paper in (self.papers if papers is None else papers))

    def pill(self, key, root="", link=True):
        domain = self.domains[key]
        body = '<i class="dot" aria-hidden="true"></i>' + esc(domain["label"])
        attrs = 'class="domain-pill" style="--domain:%s"' % esc(domain["color"])
        if link:
            return '<a %s href="%stopics/%s/index.html">%s</a>' % (attrs, root, esc(key), body)
        return '<span %s>%s</span>' % (attrs, body)

    def shell(self, title, description, root, content, active="home"):
        site = self.settings["site"]
        menu = [("home", "index.html", "研究概览", "01"), ("library", "library/index.html", "全部论文", "02"),
                ("archive", "archive/index.html", "历史日报", "03"), ("learn", "learn/index.html", "训练与学习", "04")]
        nav = "".join('<a href="%s%s" %s><span>%s</span><b>%s</b></a>' % (
            root, path, 'aria-current="page"' if key == active else "", number, label,
        ) for key, path, label, number in menu)
        groups = []
        for group in ("研究主线", "交叉拓展"):
            links = "".join('<a class="topic-link" href="%stopics/%s/index.html" %s><i class="dot" style="--domain:%s" aria-hidden="true"></i><span>%s</span><small>%d</small></a>' % (
                root, key, 'aria-current="page"' if active == key else "", domain["color"], esc(domain["label"]), self.count_domain(key),
            ) for key, domain in self.domains.items() if domain["group"] == group)
            groups.append('<div class="nav-group"><p>%s</p>%s</div>' % (group, links))
        return '''<!doctype html>
<html lang="zh-CN" data-lang="zh" data-theme="light">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="%s"><meta name="theme-color" content="#f5f7fa">
<meta property="og:title" content="%s"><meta property="og:description" content="%s">
<title>%s · %s</title>
<link rel="icon" href="data:image/svg+xml,%%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%%3E%%3Crect width='40' height='40' rx='11' fill='%%23156c65'/%%3E%%3Ccircle cx='20' cy='20' r='11' fill='none' stroke='white' stroke-width='2'/%%3E%%3Cpath d='M20 8v12l8 4' fill='none' stroke='white' stroke-width='2'/%%3E%%3C/svg%%3E">
<link rel="stylesheet" href="%sassets/app.css"><script src="%sassets/app.js" defer></script>
</head>
<body data-root="%s">
<a class="skip-link" href="#content">跳到内容</a>
<aside class="sidebar" id="site-navigation" aria-label="主导航">
<button class="sidebar-close icon-button" type="button" data-menu aria-controls="site-navigation" aria-expanded="false">关闭目录</button>
<a class="brand" href="%sindex.html"><span class="brand-mark" aria-hidden="true">R</span><span>GNSS × AI<b>研究雷达 / RESEARCH RADAR</b></span></a>
<nav class="primary-nav">%s</nav>%s
<div class="nav-group"><p>我的阅读</p><a class="topic-link" href="%slibrary/index.html?saved=1"><span>我的收藏</span><small data-saved-count>0</small></a><a class="topic-link" href="%slibrary/index.html?reading=unread"><span>待阅读</span><span aria-hidden="true">→</span></a></div>
<div class="sidebar-note">从空间观测到智能行动。<br>保留来源，建立自己的研究脉络。</div>
</aside>
<div class="workspace">
<header class="topbar"><button class="menu-toggle icon-button" type="button" aria-controls="site-navigation" aria-expanded="false" data-menu>目录</button><span class="topbar-label">RESEARCH WORKSPACE</span>
<form class="global-search" action="%slibrary/index.html" method="get" role="search"><label class="sr-only" for="global-search">搜索全部历史论文</label><input id="global-search" name="q" type="search" placeholder="搜索全部历史：ROTI、LoRA、VLA…"><kbd>/</kbd></form>
<div class="topbar-actions"><button type="button" class="icon-button" data-language aria-pressed="false" title="切换论文标题语言">中 / EN</button><button class="icon-button" data-theme-toggle type="button" aria-label="切换明暗主题">明 / 暗</button></div></header>
<main id="content" class="content">%s</main>
<footer class="footer"><span>%s · 公开研究资料导航</span><span>AI 解读需核验 · <a href="%sabout/index.html">来源与更新说明</a></span></footer>
</div>
<div class="toast" role="status" aria-live="polite" data-toast hidden></div>
</body></html>
''' % (esc(description), esc(title), esc(description), esc(title), esc(site["name"]), root, root, root,
       root, nav, "".join(groups), root, root, root, content, esc(site["name"]), root)

    def heading(self, eyebrow, title, description, aside=""):
        return '<section class="page-heading"><div><p class="eyebrow">%s</p><h1>%s</h1><p class="lede">%s</p></div>%s</section>' % (
            esc(eyebrow), esc(title), esc(description), aside,
        )

    def card(self, paper, root):
        search = " ".join([paper["id"], paper["title_zh"], paper["title_en"], paper["abstract_en"],
                           paper["one_liner"], " ".join(paper["authors"]), " ".join(paper["tags"]),
                           " ".join(self.domains[key]["label"] for key in paper["domains"]),
                           " ".join(self.lenses[key]["label"] for key in paper["lenses"])])
        tags = "".join('<a class="tag" href="%slibrary/index.html?q=%s">%s</a>' % (
            root, urllib.parse.quote(tag), esc(tag),
        ) for tag in paper["tags"][:4])
        pills = "".join(self.pill(key, root) for key in paper["domains"][:2])
        authors = ", ".join(paper["authors"][:3]) + (" et al." if len(paper["authors"]) > 3 else "")
        return '''<article class="paper-card" data-paper-card data-id="%s" data-domains="%s" data-lenses="%s" data-date="%s" data-collected="%s" data-issues="%s" data-score="%s" data-status="%s" data-search="%s" style="--domain:%s">
<div class="card-top"><div class="pills">%s</div><span class="status-badge status-%s">%s</span></div>
<h3><a href="%spapers/%s/index.html">%s</a></h3><p class="paper-authors">%s</p>
<p class="paper-summary">%s</p><div class="tags">%s</div>
<div class="card-meta"><span>发表 %s</span><span>收录 %s</span><span title="初筛或整理分数，不同编选方式不可直接比较">匹配 %s</span></div>
<div class="card-bottom"><a class="read-link" href="%spapers/%s/index.html">阅读笔记 <span aria-hidden="true">↗</span></a><div class="reading-actions"><button type="button" data-save="%s" aria-pressed="false">收藏</button><button type="button" data-read="%s" aria-pressed="false">标为已读</button></div></div>
</article>''' % (
            esc(paper["id"]), esc(" ".join(paper["domains"])), esc(" ".join(paper["lenses"])),
            esc(paper["date"]), esc(paper["collected"]), esc(" ".join(paper["issues"])), paper["score"],
            paper["status"], esc(search), self.domains[paper["domain"]]["color"], pills,
            paper["status"], STATUS_LABELS[paper["status"]], root, esc(paper["slug"]),
            dual(paper["title_zh"], paper["title_en"]), esc(authors), dual(paper["one_liner"], paper["one_liner_en"]),
            tags, paper["date"], paper["collected"], paper["score"], root, paper["slug"], esc(paper["id"]), esc(paper["id"]),
        )

    def browser(self, papers, root, default_domain="all", scope="全部历史论文"):
        domain_options = '<option value="all">全部领域</option>' + "".join('<option value="%s" %s>%s</option>' % (
            key, "selected" if key == default_domain else "", esc(value["label"]),
        ) for key, value in self.domains.items())
        lens_options = '<option value="all">全部交叉视角</option>' + "".join('<option value="%s">%s</option>' % (key, esc(lens["label"])) for key, lens in self.lenses.items())
        months = sorted({date[:7] for paper in papers for date in paper["issues"]}, reverse=True)
        month_options = '<option value="all">所有收录月份</option>' + "".join('<option value="%s">%s</option>' % (month, month) for month in months)
        cards = "".join(self.card(paper, root) for paper in papers)
        return '''<section class="paper-browser" data-browser data-default-domain="%s" data-page-size="12" aria-label="%s">
<form class="filter-panel" data-filters>
<div class="filter-search"><label for="paper-search">搜索%s</label><input id="paper-search" data-field="q" type="search" placeholder="标题、作者、摘要、标签、arXiv ID" autocomplete="off"></div>
<div class="filter-controls"><label>研究领域<select data-field="domain">%s</select></label><label>交叉视角<select data-field="lens">%s</select></label><label>收录月份<select data-field="month">%s</select></label><label>内容状态<select data-field="status"><option value="all">全部状态</option><option value="deep">图文精读示范</option><option value="ai">AI 解读</option><option value="curated">整理摘要</option><option value="metadata">检索初筛</option></select></label><label>阅读状态<select data-field="reading"><option value="all">全部阅读状态</option><option value="unread">未读</option><option value="read">已读</option></select></label><label>排序<select data-field="sort"><option value="newest">发表时间 · 新到旧</option><option value="collected">收录时间 · 新到旧</option><option value="score">匹配度 · 高到低</option><option value="oldest">发表时间 · 旧到新</option></select></label></div>
<div class="filter-footer"><label class="check-label"><input data-field="saved" type="checkbox">只看收藏</label><button type="button" class="text-button" data-reset>重置筛选</button><span class="local-note">收藏与已读保存在本设备，可导出迁移。</span></div>
</form>
<div class="results-toolbar"><p class="result-count" aria-live="polite" data-result-count>共 %d 篇</p><div class="view-toggle" aria-label="论文显示方式"><button data-view="cards" type="button" aria-pressed="true">卡片</button><button data-view="list" type="button" aria-pressed="false">紧凑列表</button></div></div>
<noscript><p class="notice">JavaScript 未启用：下面显示所有论文。筛选、收藏与分页需启用 JavaScript。</p></noscript>
<div class="paper-grid" data-paper-grid>%s</div>
<div class="empty-state" data-empty hidden><h3>没有符合条件的论文</h3><p>试着减少筛选条件，或到全部论文库检索其他期号。</p><button type="button" class="button" data-reset>重置筛选</button></div>
<nav class="pagination" aria-label="结果分页" data-pagination hidden><button type="button" data-prev>上一页</button><span data-page-label></span><button type="button" data-next>下一页</button></nav>
</section>''' % (default_domain, esc(scope), esc(scope), domain_options, lens_options, month_options, len(papers), cards)

    def retrieval_label(self):
        records = self.status.get("queries", [])
        state = self.status.get("retrieval_status", "unknown")
        label = {"ok": "检索完成", "partial": "部分检索失败", "failed": "检索失败",
                 "already_checked": "今日已检查"}.get(state, "等待检查")
        if records:
            label += "（%d/%d 路成功）" % (sum(item.get("status") == "ok" for item in records), len(records))
        return label

    def status_panel(self):
        status = self.status
        state = status.get("ai", {}).get("state", "unknown")
        ai_label = {"ready": "DeepSeek 已配置", "missing_key": "DeepSeek 待配置密钥", "disabled": "AI 解读已关闭",
                    "invalid_key": "DeepSeek 密钥无效", "insufficient_balance": "DeepSeek 余额不足"}.get(state, "AI 状态待检查")
        result = {"updated": "本期已更新", "already_checked": "今日已检查", "no_new_papers": "已检查，暂无新增",
                  "retrieval_failed": "检索失败，保留上期"}.get(status.get("result"), "等待更新检查")
        if status.get("retrieval_status") == "partial":
            result = "部分更新 · 检索待补齐"
        return '<aside class="update-panel"><p class="eyebrow">UPDATE STATUS</p><h2>%s</h2><p><span class="status-dot" aria-hidden="true"></span>%s</p><dl><div><dt>最近检查</dt><dd>%s</dd></div><div><dt>最新日报</dt><dd>%s</dd></div><div><dt>检索完整性</dt><dd>%s</dd></div><div><dt>更新计划</dt><dd>00:17 / 03:17 / 06:17</dd></div></dl><small>北京时间。提前触发并补跑；平台可能延迟，以实际检查记录为准。检索失败不代表没有新论文。</small></aside>' % (
            result, ai_label, esc(timestamp(status.get("checked_at"))), self.latest["edition"]["date"], esc(self.retrieval_label()),
        )

    def home(self):
        root = ""
        date = self.latest["edition"]["date"]
        newest = self.issues[date]
        hero = '<section class="home-hero"><div><p class="eyebrow">CONNECT IDEAS. BUILD CONTEXT.</p><h1>让论文成为<br><span>可连接的研究线索。</span></h1><p class="lede">以 GNSS 与电离层为主线，连接科学 AI、工程感知、具身智能和模型训练。不止看今天，也能找回以前。</p><div class="hero-actions"><a class="button primary" href="library/index.html">进入全部论文库 <span aria-hidden="true">→</span></a><a class="button" href="learn/index.html">模型训练学习路径</a></div></div>%s</section>' % self.status_panel()
        stats = '<div class="overview-stats">' + "".join('<div><strong>%s</strong><span>%s</span></div>' % pair for pair in (
            (str(len(self.papers)), "累计论文"), (str(len(self.editions)), "历史日报"), (str(len(self.domains)), "研究方向"),
            (str(sum(paper["status"] in ("ai", "curated", "deep") for paper in self.papers)), "有中文整理"),
        )) + '</div>'
        feature = ""
        if self.deep_reads:
            sample_id = max(self.deep_reads, key=lambda key: self.deep_reads[key]["checked_on"])
            sample = self.catalogue[sample_id]
            feature = '<section class="deep-feature" aria-label="图文精读示范"><div><p class="eyebrow">DEEP READING / 单篇示范</p><h2>%s</h2><p>整体概括 → Research gap → 算法图解与公式 → 实验提升与局限。独立全文导读，不替代其他论文的摘要级解读。</p></div><a class="button primary" href="papers/%s/index.html">打开图文精读 →</a></section>' % (esc(sample["title_zh"]), esc(sample["slug"]))
        domains = []
        for key, domain in self.domains.items():
            domains.append('<a class="domain-tile" href="topics/%s/index.html" style="--domain:%s"><span class="tile-top"><b>%s</b><small>%s</small></span><h3>%s</h3><p>%s</p><span class="tile-bottom">%d 篇历史论文 <b aria-hidden="true">↗</b></span></a>' % (
                key, domain["color"], esc(domain["short"]), esc(domain["group"]), esc(domain["label"]), esc(domain["desc"]), self.count_domain(key),
            ))
        lenses = "".join('<a class="lens-link" href="library/index.html?lens=%s">%s <span aria-hidden="true">↗</span></a>' % (key, esc(lens["label"])) for key, lens in self.lenses.items())
        latest_header = '<div class="section-heading"><div><p class="eyebrow">LATEST ISSUE / %s</p><h2>最新日报</h2></div><a class="text-link" href="daily/%s/index.html">查看第 %s 期 →</a></div>' % (date, date, esc(self.latest["edition"]["number"]))
        content = hero + stats + feature + '<section class="section" id="domains"><div class="section-heading"><div><p class="eyebrow">RESEARCH AREAS</p><h2>六条主线，交叉阅读</h2></div><span class="muted">领域页汇总全部历史，不限最新一期</span></div><div class="domain-grid">' + "".join(domains) + '</div><div class="lens-strip"><strong>从方法找连接</strong>' + lenses + '</div></section>'
        content += '<section class="section" id="papers">' + latest_header + self.browser(newest, root, scope="本期论文") + '</section>'
        return self.shell("研究概览", self.settings["site"]["subtitle"], root, content)

    def library(self, domain=None):
        root = "../../" if domain else "../"
        papers = self.papers if not domain else [paper for paper in self.papers if domain in paper["domains"]]
        if domain:
            meta = self.domains[domain]
            heading = self.heading("RESEARCH AREA / " + meta["en"], meta["label"], meta["long"])
            active = domain
        else:
            heading = self.heading("PAPER LIBRARY", "全部论文，一处检索。", "跨期搜索标题、作者、摘要与标签。领域和交叉视角可以组合筛选；链接可直接收藏或分享。")
            active = "library"
        tools = '<details class="reading-tools"><summary>我的阅读数据：导入 / 导出</summary><div><p>仅保存在当前浏览器，不自动跨设备同步。导出 JSON 后可在另一台设备导入；导入会合并，不会清空已有记录。</p><button class="button" type="button" data-export-reading>导出收藏与已读</button><label class="button import-label">导入阅读数据<input type="file" accept="application/json,.json" data-import-reading></label></div></details>'
        content = heading + tools + self.browser(papers, root, scope="本领域历史" if domain else "全部历史论文")
        return self.shell(self.domains[domain]["label"] if domain else "全部论文", "全历史跨学科论文库", root, content, active)

    def issue(self, view):
        date = view["edition"]["date"]
        index = self.editions.index(view)
        previous = self.editions[index + 1] if index + 1 < len(self.editions) else None
        following = self.editions[index - 1] if index else None
        navigation = '<nav class="issue-navigation" aria-label="日报翻页">'
        navigation += '<a href="../%s/index.html">← %s</a>' % (previous["edition"]["date"], previous["edition"]["date"]) if previous else '<span>已到最早一期</span>'
        navigation += '<a href="../../archive/index.html">全部期号</a>'
        navigation += '<a href="../%s/index.html">%s →</a>' % (following["edition"]["date"], following["edition"]["date"]) if following else '<span>最新一期</span>'
        navigation += '</nav>'
        heading = self.heading("DAILY RESEARCH / 第 %s 期" % view["edition"]["number"], date + " · 研究日报", "按当天收录内容回看。后续更新不会删除旧论文；相同论文的阅读笔记可能随整理进度补充。")
        papers = self.issues[date]
        counts = Counter(paper["status"] for paper in papers)
        overview = '<div class="issue-summary"><strong>%d 篇论文</strong><span>图文精读示范 %d</span><span>AI 解读 %d</span><span>整理摘要 %d</span><span>检索初筛 %d</span></div>' % (len(papers), counts["deep"], counts["ai"], counts["curated"], counts["metadata"])
        if view["edition"].get("retrieval_status") in ("partial", "failed"):
            overview += '<p class="notice">本期检索不完整：部分来源限流、超时或失败，不代表其他方向没有论文。后续补跑会继续检查，并保留已收录内容。</p>'
        return self.shell(date + " 日报", "跨学科研究日报", "../../", navigation + heading + overview + self.browser(papers, "../../", scope="本期论文"), "archive")

    def archive(self):
        months = sorted({view["edition"]["date"][:7] for view in self.editions}, reverse=True)
        quick = '<nav class="month-links" aria-label="月份跳转">' + "".join('<a href="#month-%s">%s</a>' % (month, month) for month in months) + '</nav>'
        controls = '<div class="archive-filters"><label>按月份<select data-archive-month><option value="all">所有月份</option>' + "".join('<option value="%s">%s</option>' % (month, month) for month in months) + '</select></label><label>按研究方向<select data-archive-domain><option value="all">全部方向</option>' + "".join('<option value="%s">%s</option>' % (key, esc(value["label"])) for key, value in self.domains.items()) + '</select></label><span class="muted" data-archive-count></span></div>'
        sections = []
        for month in months:
            views = [view for view in self.editions if view["edition"]["date"].startswith(month)]
            date_map = {view["edition"]["date"]: view for view in views}
            year, number = map(int, month.split("-"))
            rows = []
            for week in calendar.monthcalendar(year, number):
                cells = []
                for day in week:
                    date = "%s-%02d" % (month, day)
                    if not day:
                        cells.append('<td class="calendar-blank"></td>')
                    elif date in date_map:
                        cells.append('<td><a href="../daily/%s/index.html" aria-label="%s，%d 篇论文">%d<i aria-hidden="true"></i></a></td>' % (date, date, len(date_map[date]["papers"]), day))
                    else:
                        cells.append('<td><span>%d</span></td>' % day)
                rows.append('<tr>' + "".join(cells) + '</tr>')
            cal = '<table class="calendar"><caption>%s · 有圆点的日期有日报</caption><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (month, "".join('<th scope="col">%s</th>' % day for day in "一二三四五六日"), "".join(rows))
            items = []
            for view in views:
                date = view["edition"]["date"]
                papers = self.issues[date]
                keys = [key for key in self.domains if self.count_domain(key, papers)]
                pills = "".join(self.pill(key, "../", link=False) for key in keys)
                items.append('<article class="archive-row" data-archive-item data-month="%s" data-domains="%s"><div><a class="archive-date" href="../daily/%s/index.html">%s <span aria-hidden="true">↗</span></a><span class="muted">第 %s 期 · %d 篇</span></div><div class="pills">%s</div></article>' % (month, " ".join(keys), date, date, esc(view["edition"]["number"]), len(papers), pills))
            sections.append('<section class="archive-month" id="month-%s" data-archive-section><div class="section-heading"><h2>%s</h2><span class="muted">%d 期日报</span></div><div class="archive-layout">%s<div>%s</div></div></section>' % (month, month, len(views), cal, "".join(items)))
        content = self.heading("RESEARCH ARCHIVE", "历史不再藏在翻页里。", "按月份、日期或领域找回日报。圆点代表已发布期号；没有日报的日期不表示当天任务一定没有运行。")
        content += quick + controls + '<div data-archive>' + "".join(sections) + '</div><p class="empty-state" data-archive-empty hidden>这个月份或方向暂时没有日报。</p>'
        return self.shell("历史日报", "按月份和领域查看全部研究日报", "../", content, "archive")

    def section(self, key, title, body):
        return '<section class="reading-section" id="%s"><h2>%s</h2>%s</section>' % (key, esc(title), body)

    def paper(self, paper):
        root = "../../"
        status = paper["status"]
        pills = "".join(self.pill(key, root) for key in paper["domains"])
        issue_links = "".join('<a href="../../daily/%s/index.html">%s</a>' % (date, date) for date in paper["issues"])
        actions = '<div class="paper-action-bar"><a class="button primary" href="%s">arXiv 原文 ↗</a><a class="button" href="%s">PDF</a><button class="button" type="button" data-save="%s" aria-pressed="false">收藏</button><button class="button" type="button" data-read="%s" aria-pressed="false">标为已读</button><button class="button" type="button" data-copy-citation>复制引用</button></div>' % (
            esc(safe_link(paper["links"]["abs"])), esc(safe_link(paper["links"]["pdf"])), esc(paper["id"]), esc(paper["id"]),
        )
        original_title = '<p class="original-title" lang="en">%s</p>' % esc(paper["title_en"]) if paper["title_zh"].strip() != paper["title_en"].strip() else ""
        header = '<div class="breadcrumbs"><a href="../../library/index.html">全部论文</a><span>/</span><span>%s</span></div><header class="paper-heading"><div class="pills">%s<span class="status-badge status-%s">%s</span></div><h1>%s</h1>%s<p class="paper-authors">%s</p><div class="paper-dates"><span>发表 %s</span><span>首次收录 %s</span><span>arXiv:%s</span></div>%s</header>' % (
            esc(paper["id"]), pills, status, STATUS_LABELS[status], dual(paper["title_zh"], paper["title_en"]), original_title,
            esc(", ".join(paper["authors"])), paper["date"], paper["collected"], esc(paper["id"]), actions,
        )
        if status == "deep":
            citation = {"id": paper["id"], "title": paper["title_en"], "authors": paper["authors"], "year": paper["date"][:4], "url": paper["links"]["abs"]}
            payload = json.dumps(citation, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
            content = header + render_deep_read(paper["deep_read"], paper["abstract_en"], issue_links)
            content += '<script type="application/json" id="citation-data">%s</script>' % payload
            page = self.shell(paper["title_zh"], paper["one_liner"], root, content, "library")
            resources = '<link rel="stylesheet" href="../../assets/deep-reading.css"><script src="../../assets/deep-reading.js" defer></script>'
            return page.replace('</head>', resources + '</head>', 1)
        sections = []
        if status == "ai":
            analysis, ai = paper["analysis"], paper["ai"]
            scope = "仅基于摘要" if ai.get("scope") == "abstract" else "摘要与已读取的网页摘录（非完整全文）"
            note = '<div class="notice"><strong>AI 生成，待人工核验</strong><p>%s · %s · %s。引文匹配不代表结论已被独立验证。</p></div>' % (esc(ai.get("model", "DeepSeek")), scope, esc(timestamp(ai.get("generated_at"))))
            sections.append(self.section("summary", "先看结论与问题", paragraphs([analysis["summary"], analysis["question"]])))
            sections.append(self.section("method", "方法改变了什么", paragraphs([analysis["method"]])))
            findings = []
            for finding in analysis["findings"]:
                findings.append('<div class="evidence"><p>%s</p><blockquote lang="en">%s</blockquote><a href="%s">证据 %s ↗</a></div>' % (esc(finding["statement"]), esc(finding["quote"]), esc(safe_link(finding["url"])), esc(finding["source"])))
            sections.append(self.section("results", "结果与证据", "".join(findings) or '<p class="muted">没有提取到通过引文校验的独立结果，请核对原文。</p>'))
            sections.append(self.section("limits", "局限与迁移启发", bullet_list(analysis["limitations"]) + '<div class="transfer-note"><h3>迁移建议 · 推断，不是论文结论</h3><p>%s</p></div>' % esc(analysis["transfer"])))
            sections.append(self.section("practice", "训练与复现时先检查", bullet_list(analysis["practical_steps"])))
        elif status == "curated":
            note = '<div class="notice"><strong>摘要级整理，不等于全文精读</strong><p>以下保留既有中文笔记与指标，未逐篇复核全文。需要引用数字、实验配置或方法结论时，请回到原文。</p></div>'
            sections.append(self.section("summary", "速读与研究问题", paragraphs([paper.get("lead_zh", paper["one_liner"])] + paper.get("problem", []))))
            sections.append(self.section("method", "方法与关键环节", paragraphs(paper.get("method", []))))
            essence = "".join('<div><h3>%s</h3><p>%s</p></div>' % (esc(item["h"]), esc(item["p"])) for item in paper.get("essence", []))
            sections.append(self.section("essence", "方法拆解", '<div class="essence-grid">' + essence + '</div>'))
            metrics = "".join('<div><strong>%s</strong><span>%s</span></div>' % (esc(item["value"]), esc(item["label"])) for item in paper.get("metrics", []))
            sections.append(self.section("results", "原有整理中的结果", '<div class="metric-grid">' + metrics + '</div>' + paragraphs(paper.get("results", []))))
            sections.append(self.section("limits", "边界与研究连接", paragraphs(paper.get("limits", [])) + '<div class="transfer-note"><h3>研究启发 · 需验证</h3>' + paragraphs(paper.get("relevance", [])) + '</div>'))
        else:
            note = '<div class="notice"><strong>检索条目，尚无 AI 中文解读</strong><p>关键词初筛不代表质量推荐。可先阅读原始摘要，或收藏后再核对全文。当前解读状态：%s。</p></div>' % esc(paper.get("analysis_status", "未生成"))
            sections.append(self.section("summary", "如何阅读这条记录", '<p>先核对研究对象、输入数据和评价条件，再判断与定位、电离层、训练或机器人任务的连接。这里没有把摘要自动补写成实验结论。</p>'))
        abstract_title = "提供的英文摘要 / 摘要摘录" if status == "curated" else "arXiv 原文摘要"
        sections.append(self.section("abstract", abstract_title, '<div class="abstract" lang="en">%s</div>' % esc(paper["abstract_en"])))
        sources = '<ul class="source-list"><li><a href="%s">arXiv 摘要页 ↗</a></li><li><a href="%s">arXiv PDF ↗</a></li>' % (esc(safe_link(paper["links"]["abs"])), esc(safe_link(paper["links"]["pdf"])))
        if paper["links"].get("code"):
            sources += '<li><a href="%s">代码仓库 ↗</a></li>' % esc(safe_link(paper["links"]["code"]))
        for source in paper.get("ai", {}).get("sources", []):
            sources += '<li><a href="%s">%s · %s ↗</a></li>' % (esc(safe_link(source["url"])), esc(source["id"]), esc(source["title"]))
        sources += '</ul><p class="muted">收录于日报：%s</p>' % issue_links
        sections.append(self.section("sources", "来源与收录历史", sources))
        toc_links = [("summary", "速读"), ("method", "方法"), ("results", "结果"), ("limits", "边界"), ("abstract", "原文摘要"), ("sources", "来源")]
        toc = '<nav class="reading-toc" aria-label="文章目录"><p class="eyebrow">ON THIS PAGE</p>' + "".join('<a href="#%s">%s</a>' % (key, title) for key, title in toc_links if any('id="%s"' % key in section for section in sections)) + '</nav>'
        related = [item for item in self.papers if item["id"] != paper["id"] and set(item["domains"]) & set(paper["domains"])][:3]
        related_html = '<section class="section"><div class="section-heading"><h2>沿着这条线继续读</h2><a href="../../library/index.html">全部论文 →</a></div><div class="paper-grid">' + "".join(self.card(item, root) for item in related) + '</div></section>'
        citation = {"id": paper["id"], "title": paper["title_en"], "authors": paper["authors"], "year": paper["date"][:4], "url": paper["links"]["abs"]}
        payload = json.dumps(citation, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
        content = header + note + '<div class="reading-layout"><div class="reading-body">' + "".join(sections) + '</div>' + toc + '</div>' + related_html
        content += '<script type="application/json" id="citation-data">%s</script>' % payload
        return self.shell(paper["title_zh"], paper["one_liner"], root, content, "library")

    def learning(self):
        learning = load_json(DATA / "learning.json")
        modules = []
        for item in learning["modules"]:
            resources = "".join('<a href="%s">%s ↗</a>' % (esc(safe_link(source["url"])), esc(source["title"])) for source in item["resources"])
            modules.append('<section class="learning-card" id="%s"><div class="learning-top"><span class="status-badge">%s</span><a href="../library/index.html?q=%s">找相关论文 →</a></div><h2>%s</h2><p class="learning-goal">%s</p>%s<div class="learning-callout"><strong>连接到你的主线</strong><p>%s</p></div><p class="learning-pitfall"><strong>容易踩的坑：</strong>%s</p><div class="resource-links">%s</div></section>' % (
                item["id"], esc(item["level"]), urllib.parse.quote(item["query"]), esc(item["title"]), esc(item["goal"]), bullet_list(item["steps"]), esc(item["transfer"]), esc(item["pitfall"]), resources,
            ))
        content = self.heading("LEARN · TRAIN · TRANSFER", learning["title"], learning["intro"])
        content += '<div class="notice">这些是人工组织的学习路线与官方资料入口，不是每天由 AI 生成的课程，也不承诺特定实验结果。</div><div class="learning-grid">' + "".join(modules) + '</div>'
        return self.shell("训练与学习", learning["intro"], "../", content, "learn")

    def about(self):
        ai = self.status.get("ai", {})
        content = self.heading("SOURCES & OPERATIONS", "知道内容怎么来，也知道它的边界。", "这不是论文质量排行榜。我们把检索、AI 解读和原有整理分开标记，并保留来源与实际运行状态。")
        content += '<div class="about-grid"><section class="panel"><h2>把内容深度分开标记</h2><ul><li>检索初筛：原始元数据与摘要，未生成中文解读。</li><li>AI 解读：DeepSeek 基于摘要或网页摘录生成，带来源与证据引用，仍需人工核验。</li><li>整理摘要：保留原有中文笔记，不表示已精读全文。</li><li>图文精读示范：独立保存的版本化全文导读，含图解、公式、实验口径与原文定位；仍不等于独立复现。目前仅做单篇示范，不代表每日文章都已达到这个深度。</li></ul></section><section class="panel"><h2>更新与时区</h2><p>北京时间 00:17 首次触发，03:17、06:17 补跑。同日去重，保留历史。GitHub Actions 可能延迟，不提供严格的 08:00 服务保证。</p><p>最近检查：%s</p><p>检索状态：%s</p></section></div>' % (esc(timestamp(self.status.get("checked_at"))), esc(self.retrieval_label()))
        failed = [self.domains[item["domain"]]["label"] for item in self.status.get("queries", [])
                  if item.get("status") != "ok" and item.get("domain") in self.domains]
        if failed:
            content += '<p class="notice">尚未成功检查的来源：%s。限流或超时不表示该方向没有新论文；下一次任务会重试。</p>' % esc("、".join(failed))
        limits = self.settings["deepseek"]
        content += '<section class="panel section"><h2>DeepSeek 配置与用量</h2><p>密钥只通过 GitHub Actions Secret <code>DEEPSEEK_API_KEY</code> 传入，不在前端、不在公开 JSON，也不发送飞书原文。模型为 <code>%s</code>。</p><p>状态：<strong>%s</strong>。当日已报告输入 %s token、输出 %s token；不确定的请求预留量 %s token。</p><p>配置上限：每天解读 %s 篇、搜索 %s 次、网页读取 %s 次。token 用保守预留限制在 %s 内；具体账单以 DeepSeek 后台为准。</p><p><a href="https://api-docs.deepseek.com/guides/search">官方搜索与读取说明 ↗</a> · <a href="https://api-docs.deepseek.com/quick_start/pricing">官方实时价格 ↗</a></p></section>' % (esc(limits["model"]), esc(ai.get("state", "unknown")), ai.get("input_tokens", 0), ai.get("output_tokens", 0), ai.get("uncertain_reserved_tokens", 0), limits["daily_paper_limit"], limits["daily_search_limit"], limits["daily_fetch_limit"], limits["daily_token_limit"])
        content += '<section class="panel"><h2>阅读数据与隐私</h2><p>收藏与已读存储在浏览器 localStorage，不需要登录，不会自动发往服务器。不同设备请通过论文库里的 JSON 导入／导出合并；清理浏览器会丢失未导出的记录。</p><h2>来源与版权</h2><p>论文标题、作者与摘要来自 arXiv，版权归原作者。学习资料链接指向官方文档。页面已重写为本项目的研究工作台；最初参考了 <a href="https://github.com/haoshendong/slam3d-paper-watch">slam3d-paper-watch</a> 的日报组织形式。</p><p>关键词匹配不等于质量评分；自动引文检查也不能确认语义一定正确。重要结论请回原文。</p></section>'
        return self.shell("来源与更新说明", "来源、AI 证据边界、隐私与自动化运行说明", "../", content)

    def not_found(self):
        content = self.heading("404 / NOT FOUND", "这条线索暂时找不到。", "页面可能已移动。可以回到论文库重新搜索，或按日期查看历史日报。")
        content += '<div class="hero-actions"><a class="button primary" href="library/index.html">进入论文库</a><a class="button" href="archive/index.html">查看历史日报</a></div>'
        page = self.shell("页面不存在", "页面不存在", "", content)
        base = '<base href="%s">' % esc(self.settings["site"]["url"])
        return page.replace('<head>', '<head>' + base, 1)

    def render(self, output):
        output.mkdir(parents=True, exist_ok=True)
        pages = {"index.html": self.home(), "library/index.html": self.library(),
                 "archive/index.html": self.archive(), "learn/index.html": self.learning(),
                 "about/index.html": self.about(), "404.html": self.not_found()}
        for key in self.domains:
            pages["topics/%s/index.html" % key] = self.library(key)
        for view in self.editions:
            pages["daily/%s/index.html" % view["edition"]["date"]] = self.issue(view)
        for paper in self.papers:
            pages["papers/%s/index.html" % paper["slug"]] = self.paper(paper)
        for name, content in pages.items():
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        (output / ".nojekyll").touch()
        if output != ROOT:
            shutil.copytree(str(ROOT / "assets"), str(output / "assets"))
        return len(pages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="", help="export only public HTML/assets into a new directory")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve() if args.output else ROOT
    if output != ROOT and ROOT not in output.parents:
        parser.error("output must be inside this project")
    if output != ROOT and output.exists():
        parser.error("output already exists; use a new directory")
    site = Site()
    count = site.render(output)
    print("built %d pages, %d unique papers, %d issues -> %s" % (count, len(site.papers), len(site.editions), output))


if __name__ == "__main__":
    main()
