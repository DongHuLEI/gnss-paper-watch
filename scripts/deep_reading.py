"""Render source-linked, versioned full-text reading overlays."""

import datetime as dt
import hashlib
import html
import json
import math
import re
import urllib.parse
import xml.etree.ElementTree as ET

MATH_TAGS = {"mrow", "mi", "mn", "mo", "mtext", "mfrac", "msub", "msup", "msubsup", "msqrt", "mover", "mspace"}
MATH_ATTRS = {"mathvariant", "width"}
SECTIONS = [("overview", "整体概括"), ("gap", "Research gap"), ("method", "算法主线"),
            ("equations", "关键公式"), ("experiments", "实验怎么做"), ("results", "提升与证据"),
            ("limits", "局限与追问"), ("transfer", "连接你的研究"), ("sources", "来源与边界")]


def esc(value):
    return html.escape(str(value), quote=True)


def checked_math(value):
    node = ET.fromstring('<math>' + value + '</math>')
    for element in node.iter():
        if element.tag != "math" and element.tag not in MATH_TAGS:
            raise ValueError("unsupported MathML element: " + element.tag)
        if set(element.attrib) - MATH_ATTRS:
            raise ValueError("unsupported MathML attribute")
        for key, item in element.attrib.items():
            if key == "width" and not re.fullmatch(r"\d+(?:\.\d+)?em", item):
                raise ValueError("invalid MathML spacing")
            if key == "mathvariant" and item not in ("normal", "script", "double-struck"):
                raise ValueError("invalid MathML variant")
    return value


def equation_asset(data, equation, field):
    digest = hashlib.sha256(equation[field].encode("utf-8")).hexdigest()[:12]
    return "assets/deep-reading/%s/%s-%s.svg" % (data["paper_id"], equation["id"], digest)


def validate_formula_asset(path):
    if not path.is_file():
        raise ValueError("missing formula asset; regenerate with scripts/render_equations.cjs: " + str(path))
    root = ET.parse(str(path)).getroot()
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("invalid formula SVG")
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] not in ("svg", "g", "path", "rect", "line", "text", "title"):
            raise ValueError("unexpected formula SVG element")
        for key, value in element.attrib.items():
            name = key.rsplit("}", 1)[-1].lower()
            if name.startswith("on") or name in ("href", "src") or "url(" in value.lower():
                raise ValueError("active content in formula SVG")


def load_deep_reads(directory):
    result = {}
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["paper_id"] != path.stem or data["paper_id"] in result or not re.fullmatch(r"\d{4}\.\d{4,5}", data["paper_id"]):
            raise ValueError("invalid deep-reading identity: " + str(path))
        source = urllib.parse.urlsplit(data["source_url"])
        if source.scheme != "https" or source.netloc != "arxiv.org" or source.path != "/html/" + data["paper_id"] + "v1" or source.query or source.fragment:
            raise ValueError("invalid versioned deep-reading source")
        dt.datetime.strptime(data["checked_on"], "%Y-%m-%d")
        for reference in data["references"].values():
            if not re.fullmatch(r"[A-Za-z0-9.]+", reference["anchor"]):
                raise ValueError("invalid source anchor")
        ids = set()
        for equation in data["equations"]:
            if not re.fullmatch(r"eq-[a-z-]+", equation["id"]) or equation["id"] in ids:
                raise ValueError("invalid or duplicate equation id")
            ids.add(equation["id"])
            for field in ("mathml", "mathml_second"):
                if equation.get(field):
                    checked_math(equation[field])
                    validate_formula_asset(directory.parent.parent / equation_asset(data, equation, field))
        results = data["result_data"]
        if len(results["models"]) != 3 or results["models"][-1] != "PGFM":
            raise ValueError("deep-reading chart requires three models, with PGFM last")
        for metric in results["metrics"]:
            values = metric["average"] + [number for row in metric["leads"] for number in row]
            if len(metric["average"]) != 3 or len(metric["leads"]) != 3 or any(len(row) != len(results["lead_hours"]) for row in metric["leads"]):
                raise ValueError("deep-reading result dimensions do not match")
            if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in values):
                raise ValueError("invalid deep-reading result")
        result[data["paper_id"]] = data
    return result


def refs(data, keys):
    return '<div class="dr-refs">' + "".join('<a href="%s#%s">%s ↗</a>' % (
        esc(data["source_url"]), esc(data["references"][key]["anchor"]), esc(data["references"][key]["label"]),
    ) for key in keys) + '</div>'


def paragraphs(values):
    return "".join('<p>%s</p>' % esc(value) for value in values)


def cards(items, text_key="text"):
    return '<div class="dr-cards">' + "".join('<div><h3>%s</h3><p>%s</p></div>' % (
        esc(item["title"]), esc(item[text_key]),
    ) for item in items) + '</div>'


def figure(title, graphic, caption, source_links, figure_id):
    return '<figure class="dr-figure" id="%s"><div class="dr-figure-heading"><strong>%s</strong><button class="icon-button" type="button" data-expand-figure hidden>放大图示</button></div><div class="dr-graphic">%s</div><figcaption>%s%s</figcaption></figure>' % (
        figure_id, esc(title), graphic, esc(caption), source_links,
    )


def workflow(data):
    flow = data["workflow"]
    inputs = '<ul>' + "".join('<li>%s</li>' % esc(value) for value in flow["inputs"]) + '</ul>'
    branches = "".join('<div class="dr-flow-node dr-flow-%s"><span>02 / 分支估计</span><h3>%s</h3><p>%s</p></div>' % (
        esc(item["tone"]), esc(item["title"]), esc(item["text"]),
    ) for item in flow["branches"])
    graphic = '<div class="dr-flow"><div class="dr-flow-node dr-flow-input"><span>01 / 截至预报起点已知</span><h3>历史信息</h3>%s</div><div class="dr-flow-branches">%s</div><div class="dr-flow-node dr-flow-fuse"><span>03 / 统一速度空间</span><h3>%s</h3><p>u_hat = (1 − λ) × u_data + λ × u_phys</p></div><div class="dr-flow-node dr-flow-out"><span>04 / 一小时预报</span><h3>%s</h3><p>%s</p></div><div class="dr-flow-training"><strong>只在训练时</strong><p>%s</p></div></div>' % (
        inputs, branches, esc(flow["fusion"]), esc(flow["output"]), esc(flow["rollout"]), esc(flow["training"]),
    )
    return figure("图解 01 / 先把训练与推断分开", graphic, "本站独立梳理的算法流程，非原论文图片。箭头按阅读顺序表示信息流；物理分支输出需做单位转换后再融合。", refs(data, ["architecture", "unet", "convgru", "units"]), "figure-workflow")


def path_diagram(data):
    graphic = '''<div class="dr-svg-scroll" tabindex="0" role="region" aria-label="路径教学示意，可横向滚动"><svg viewBox="0 0 760 290" role="img" aria-label="本站教学示意：左侧由两个端点线性插值，右侧的均值路径经过物理中间状态；横轴都是一次一小时转移内的流坐标 τ。">
<text x="30" y="29" class="dr-svg-title">端点决定均值</text><text x="409" y="29" class="dr-svg-title">物理中间态引导均值</text>
<path d="M43 68V231H348 M414 68V231H724" class="dr-axis"></path>
<path d="M60 207L326 92" class="dr-linear"></path>
<path d="M431 207C470 207 477 92 518 112S578 196 614 151S667 60 700 92" class="dr-path-band"></path>
<path d="M431 207C470 207 477 92 518 112S578 196 614 151S667 60 700 92" class="dr-physical-path"></path>
<circle cx="60" cy="207" r="5" class="dr-endpoint"></circle><circle cx="326" cy="92" r="5" class="dr-endpoint"></circle>
<circle cx="431" cy="207" r="5" class="dr-endpoint"></circle><circle cx="518" cy="112" r="5" class="dr-midpoint"></circle><circle cx="614" cy="151" r="5" class="dr-midpoint"></circle><circle cx="700" cy="92" r="5" class="dr-endpoint"></circle>
<text x="48" y="254">τ=0</text><text x="303" y="254">τ=1</text><text x="419" y="254">τ=0</text><text x="677" y="254">τ=1</text>
<text x="122" y="278">Δt = 1 h</text><text x="500" y="278">Δt = 1 h</text>
<text x="104" y="100">仅约束两端</text><text x="490" y="62">示意：非实测轨迹</text>
</svg></div>'''
    return figure("图解 02 / 为什么要改训练路径？", graphic, data["path_note"], refs(data, ["mean", "path"]), "figure-path")


def equation_card(data, item, index):
    formula = ""
    for field in ("mathml", "mathml_second"):
        if item.get(field):
            formula += '<div class="dr-equation-scroll" tabindex="0" role="region" aria-label="公式，可横向滚动"><img class="dr-formula-image" src="../../%s" alt="%s"></div>' % (esc(equation_asset(data, item, field)), esc(item["accessible"]))
    symbols = "".join('<div><dt>%s</dt><dd>%s</dd></div>' % (esc(symbol["symbol"]), esc(symbol["text"])) for symbol in item["symbols"])
    return '<section class="dr-equation" id="%s"><div class="dr-equation-top"><span>核心式 %02d</span><span>%s</span></div><h3>%s</h3>%s<p>%s</p><details><summary>符号与实现提醒</summary><dl class="dr-symbols">%s</dl><p class="dr-caution">%s</p></details>%s</section>' % (
        esc(item["id"]), index, esc(item["number"]), esc(item["title"]), formula, esc(item["meaning"]), symbols, esc(item["caution"]), refs(data, item["refs"]),
    )


def result_svg(results, metric, scope):
    values = metric["average"] if scope == "average" else [row[-1] for row in metric["leads"]]
    maximum = max(values) * 1.26
    heading = "1–24 h 全时效平均" if scope == "average" else "24 h 单点"
    title = '%s · %s / %s，越低越好' % (heading, metric["label"], metric["unit"])
    svg = ['<svg viewBox="0 0 650 245" role="img" aria-label="%s"><text x="22" y="29" class="dr-svg-title">%s</text>' % (esc(title), esc(title))]
    for i, (model, value) in enumerate(zip(results["models"], values)):
        y, width = 62 + i * 53, value / maximum * 425
        svg.append('<text x="22" y="%s">%s</text><rect x="132" y="%s" width="%.2f" height="27" rx="4" class="dr-bar dr-series-%s"></rect><text x="%.2f" y="%s" class="dr-value">%.3f</text>' % (
            y + 19, esc(model), y, width, i, 142 + width, y + 19, value,
        ))
    reduction = (1 - values[2] / values[0]) * 100
    svg.append('<text x="22" y="231">按表中数值计算，PGFM 相对 ConvLSTM 下降约 %.1f%%</text></svg>' % reduction)
    return ''.join(svg)


def result_chart(data):
    results = data["result_data"]
    controls = '<div class="dr-chart-controls" data-chart-controls hidden><label>指标<select data-result-metric>' + ''.join('<option value="%s">%s / %s</option>' % (esc(item["id"]), esc(item["label"]), esc(item["unit"])) for item in results["metrics"]) + '</select></label><div role="group" aria-label="统计口径"><button type="button" data-result-scope="average" aria-pressed="true">1–24 h 平均</button><button type="button" data-result-scope="24h" aria-pressed="false">第 24 h</button></div></div>'
    charts = []
    for metric in results["metrics"]:
        for scope in ("average", "24h"):
            hidden = "" if metric["id"] == "rmse" and scope == "average" else " hidden"
            charts.append('<div data-result-view="%s-%s"%s><div class="dr-svg-scroll" tabindex="0" role="region" aria-label="误差对比图，可横向滚动">%s</div></div>' % (esc(metric["id"]), scope, hidden, result_svg(results, metric, scope)))
    graphic = '<div data-result-chart>' + controls + ''.join(charts) + '<p class="dr-chart-announcement" data-chart-announcement aria-live="polite">当前：RMSE · 1–24 h 全时效平均，越低越好。</p><noscript><p>交互切换需启用 JavaScript；下方数据表包含全部展示数据。</p></noscript></div>'
    return figure("图解 03 / 切换口径，别把平均提升当成远期提升", graphic, results["provenance"], refs(data, ["table", "curves"]), "figure-results")


def result_table(data):
    results = data["result_data"]
    rows = []
    for metric in results["metrics"]:
        for j, hour in enumerate(results["lead_hours"]):
            cells = ''.join('<td%s>%.3f</td>' % (' class="dr-best"' if i == 2 else "", metric["leads"][i][j]) for i in range(3))
            rows.append('<tr><th scope="row">%s</th><td>%s h</td>%s</tr>' % (esc(metric["label"]), hour, cells))
        cells = ''.join('<td%s>%.3f</td>' % (' class="dr-best"' if i == 2 else "", value) for i, value in enumerate(metric["average"]))
        rows.append('<tr class="dr-average-row"><th scope="row">%s</th><td>1–24 h 平均</td>%s</tr>' % (esc(metric["label"]), cells))
    return '<details class="dr-data-details"><summary>查看数值表：选定时效与全时效平均</summary><div class="dr-table-scroll" tabindex="0" role="region" aria-label="预报误差数据，可横向滚动"><table><caption>摘录原表三种可部署模型。RMSE、MAE 单位为 TECU，nMAE 为百分数。均值行来自原表，不用五个选定时效重新求平均。</caption><thead><tr><th scope="col">指标</th><th scope="col">时效</th>%s</tr></thead><tbody>%s</tbody></table></div></details>' % (''.join('<th scope="col">%s</th>' % esc(model) for model in results["models"]), ''.join(rows))


def render(data, abstract, issue_links):
    sections = []

    def section(key, body):
        index = next(i for i, pair in enumerate(SECTIONS, 1) if pair[0] == key)
        label = dict(SECTIONS)[key]
        sections.append('<section class="dr-section" id="%s" data-reading-section><div class="dr-section-title"><span>%02d</span><h2>%s</h2></div>%s</section>' % (key, index, esc(label), body))

    overview = data["overview"]
    section("overview", '<div class="dr-big-question"><span>这篇文章在解决什么？</span><p>%s</p></div>%s%s%s' % (
        esc(overview["question"]), paragraphs([overview["answer"]]), cards(overview["takeaways"]), refs(data, ["data", "method", "table"]),
    ))
    gaps = '<div class="dr-gap-list">' + ''.join('<div><h3>%s</h3><p><b>还缺什么</b>%s</p><p><b>本文的回应</b>%s</p></div>' % (esc(item["before"]), esc(item["problem"]), esc(item["change"])) for item in data["gaps"]) + '</div>'
    section("gap", gaps + '<p class="dr-caution">%s</p>' % esc(data["gap_note"]) + refs(data, ["gap", "method"]))
    method_notes = ''.join('<div class="dr-explainer"><h3>%s</h3><p>%s</p>%s</div>' % (esc(item["title"]), esc(item["text"]), refs(data, item["refs"])) for item in data["method_notes"])
    section("method", workflow(data) + method_notes + path_diagram(data))
    section("equations", '<p>先看每条公式下面的直觉，再展开符号与实现提醒。不熟悉 Flow Matching 也可以先读融合与推断两式，之后回看路径设计。</p><p class="dr-caution">公式已预先排成矢量图，手机和旧浏览器无需联网加载公式服务。窄屏可横向滑动；省略的条件输入已在解释中说明。排版使用 MathJax 3.2.2，<a href="../../assets/deep-reading/LICENSE.txt">Apache 2.0 许可</a>；读者设备不运行该排版库。</p>' + ''.join(equation_card(data, item, i) for i, item in enumerate(data["equations"], 1)))
    setup = '<dl class="dr-setup">' + ''.join('<div><dt>%s</dt><dd>%s</dd></div>' % (esc(item["label"]), esc(item["value"])) for item in data["experiment"]) + '</dl>'
    section("experiments", setup + refs(data, ["data", "experiments"]) + '<h3 class="dr-subheading">重点比较谁？</h3>' + cards(data["comparators"]) + refs(data, ["experiments"]) + '<p class="dr-caution">指标口径：RMSE 强调大误差，MAE 是平均绝对误差；nMAE = 100 × 绝对误差之和 / 参考 TEC 绝对值之和。它不是逐格点百分比误差的平均；要复现全球结果，应核对有效网格及聚合方式。</p>' + refs(data, ["metrics"]))
    findings = ''.join('<div class="dr-finding"><h3>%s</h3><p>%s</p>%s</div>' % (esc(item["title"]), esc(item["text"]), refs(data, item["refs"])) for item in data["result_findings"])
    section("results", '<div class="dr-metric-pair"><div><strong>39.2%</strong><span>1–24 h 平均 RMSE 下降</span></div><div><strong>≈ 5.0%</strong><span>24 h 单点 RMSE 下降</span></div></div><p class="dr-small">均相对 ConvLSTM。前者为原文报告，后者由原表三位小数计算；仅在该模拟实验条件下成立。</p>' + result_chart(data) + result_table(data) + findings)
    limits = ''.join('<div class="dr-limit"><h3>%s</h3><p><span class="dr-evidence-label">原文范围</span>%s</p><p><span class="dr-question-label">本站追问</span>%s</p>%s</div>' % (esc(item["title"]), esc(item["evidence"]), esc(item["question"]), refs(data, item["refs"])) for item in data["limits"])
    section("limits", '<p>下面把作者已展示的证据与进一步需要验证的问题分开。提出追问，不等于已经证明论文有问题。</p>' + limits)
    transfer = data["transfer"]
    steps = '<ol class="dr-transfer-steps">' + ''.join('<li><h3>%s</h3><p>%s</p><p class="dr-deliverable"><strong>应交付：</strong>%s</p></li>' % (esc(item["title"]), esc(item["text"]), esc(item["deliverable"])) for item in transfer["steps"]) + '</ol>'
    questions = ''.join('<details class="dr-self-check"><summary>%s</summary><p>%s</p></details>' % (esc(item["question"]), esc(item["answer"])) for item in transfer["questions"])
    section("transfer", '<div class="dr-transfer-intro"><strong>研究建议 · 尚未验证</strong><p>%s</p></div>' % esc(transfer["intro"]) + steps + '<div class="dr-explainer"><h3>跨到工程感知与具身智能，借鉴什么？</h3><p>%s</p></div><h3 class="dr-subheading">读完能回答这三个问题吗？</h3>%s' % (esc(transfer["cross_domain"]), questions))
    section("sources", '<dl class="dr-source-meta"><div><dt>所读版本</dt><dd>arXiv:%s · %s</dd></div><div><dt>整理日期</dt><dd>%s</dd></div><div><dt>核读范围</dt><dd>%s</dd></div></dl><p>%s</p><div class="dr-source-buttons"><a class="button" href="%s">打开所读版本全文 ↗</a><a class="button" href="https://arxiv.org/abs/%s">元数据与许可说明 ↗</a></div><details class="dr-original-abstract"><summary>对照英文原始摘要</summary><div class="abstract" lang="en">%s</div></details><p class="dr-small">收录历史：%s</p><p class="dr-small">这篇导读独立保存，不替换其他论文的摘要级解读；日更重建会保留本示范。本站建议与作者结论已分开标记。</p>' % (
        esc(data["paper_id"]), esc(data["source_version"]), esc(data["checked_on"]), esc(data["scope"]), esc(data["copyright_note"]), esc(data["source_url"]), esc(data["paper_id"]), esc(abstract), issue_links,
    ))
    toc_links = ''.join('<a href="#%s"><span>%02d</span>%s</a>' % (key, i, esc(label)) for i, (key, label) in enumerate(SECTIONS, 1))
    mobile_toc = '<details class="dr-mobile-toc"><summary>本篇目录 · 9 个章节</summary><nav aria-label="移动端本篇目录">%s</nav></details>' % toc_links
    tools = '<div class="dr-toolbar"><span>全文导读示范 · 约 %s 分钟</span><a href="#results">先看实验结论 ↓</a><button type="button" class="icon-button" data-print-reading hidden>打印 / 存 PDF</button></div>' % data["reading_minutes"]
    progress = '<div class="dr-progress" data-reading-progress hidden><progress max="100" value="0" aria-label="全文导读阅读进度"></progress></div>'
    dialog = '<dialog class="dr-figure-dialog" aria-label="放大图示"><div class="dr-dialog-header"><strong>图示阅读</strong><button type="button" class="button" data-close-figure>关闭 · Esc</button></div><div class="dr-viewer-body"></div></dialog>'
    return '<div class="deep-reader" data-deep-reader>%s<div class="dr-scope"><strong>全文导读，不把摘要扩写当精读</strong><p>%s</p></div>%s%s<div class="dr-layout"><article class="dr-body">%s</article><aside class="dr-toc"><p class="eyebrow">READ THE PAPER</p><nav aria-label="全文导读目录">%s</nav><p data-reading-percent aria-live="off">阅读进度 0%%</p><a href="#content">回到文章顶部 ↑</a></aside></div>%s</div>' % (
        progress, esc(data["scope"]), tools, mobile_toc, ''.join(sections), toc_links, dialog,
    )
