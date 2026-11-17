"""Render the shared nine-chapter Skill output using the existing reading UI."""

from deep_reading import SECTIONS, equation_card, esc, layout, original_figure, refs

LABELS = {"reported": "作者报告", "interpretation": "本站解释 · AI", "proposal": "研究建议 · 未验证", "unknown": "来源未说明"}


def claim(data, item):
    evidence = ""
    if item["evidence"]:
        quotes = "".join('<blockquote lang="en">%s</blockquote>' % esc(proof["quote"]) + refs(data, [proof["source"]]) for proof in item["evidence"])
        evidence = '<details class="dr-skill-evidence"><summary>对照原文证据</summary>%s</details>' % quotes
    return '<div class="dr-skill-claim"><span class="dr-evidence-label">%s</span><h3>%s</h3><p>%s</p>%s</div>' % (esc(LABELS[item["kind"]]), esc(item["heading"]), esc(item["text"]), evidence)


def render(data, abstract, issue_links):
    sections = []
    for index, (key, title) in enumerate(SECTIONS, 1):
        if key == "sources":
            provenance = data["provenance"]
            body = '<dl class="dr-source-meta"><div><dt>所读版本</dt><dd>arXiv:%s · %s</dd></div><div><dt>生成时间</dt><dd>%s</dd></div><div><dt>生成模型</dt><dd>%s</dd></div><div><dt>Skill 版本</dt><dd>%s · %s</dd></div><div><dt>核验边界</dt><dd>%s</dd></div></dl><p>%s</p><div class="dr-source-buttons"><a class="button" href="%s">版本化原文 ↗</a><a class="button" href="https://arxiv.org/abs/%s">元数据与许可 ↗</a></div><details class="dr-original-abstract"><summary>对照原始英文摘要</summary><div class="abstract" lang="en">%s</div></details><p class="dr-small">收录历史：%s</p>' % (
                esc(data["paper_id"]), esc(data["source_version"]), esc(provenance["generated_at"]), esc(provenance["model"]), esc(data["format"]), esc(provenance["skill_sha256"][:12]), esc(data["scope"]), esc(data["copyright_note"]), esc(data["source_url"]), esc(data["paper_id"]), esc(abstract), issue_links,
            )
            body += '<p class="dr-small">原文许可：<a href="%s">查看本版本许可 ↗</a>；外部嵌入不等于任意转载授权。</p>' % esc(provenance["license_url"])
        else:
            section = next(item for item in data["sections"] if item["id"] == key)
            body = "".join(claim(data, item) for item in section["paragraphs"])
            if key == "equations":
                body += "".join(equation_card(data, item, number) for number, item in enumerate(data["equations"], 1))
            if key == "method":
                body = "".join(original_figure(data, item["reference"]) for item in data["original_figures"][:1]) + body
            if key == "results":
                body += "".join(original_figure(data, item["reference"]) for item in data["original_figures"][1:])
        sections.append('<section class="dr-section" id="%s" data-reading-section><div class="dr-section-title"><span>%02d</span><h2>%s</h2></div>%s</section>' % (key, index, esc(title), body))
    return layout(data, sections)
