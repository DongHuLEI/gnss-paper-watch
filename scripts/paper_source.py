"""Extract versioned arXiv reading evidence without publishing full-text copies."""

import hashlib
import html
import math
import re
import struct
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from deep_reading import MATH_TAGS, checked_math

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
ANCHOR = re.compile(r"[A-Za-z0-9_.:-]{1,160}")


class SourceUnavailable(ValueError):
    pass


class Node:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs or []), parent
        self.children = []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self, exclude_classes=()):
        if self.tag in ("script", "style", "annotation", "annotation-xml") or set(exclude_classes).intersection(self.attrs.get("class", "").split()):
            return ""
        if self.tag == "math" and self.attrs.get("alttext"):
            return " " + self.attrs["alttext"] + " "
        return " ".join(child.text(exclude_classes) if isinstance(child, Node) else child for child in self.children)

    def anchor(self):
        node = self
        while node:
            if ANCHOR.fullmatch(node.attrs.get("id", "")):
                return node.attrs["id"]
            node = node.parent
        return None


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                return

    def handle_data(self, value):
        self.stack[-1].children.append(value)


def normalize(value):
    return " ".join(value.split())


def source_url(paper):
    version = paper.get("version", "")
    if not re.fullmatch(r"\d{4}\.\d{4,5}", paper["id"]) or not re.fullmatch(r"v[1-9]\d*", version):
        raise SourceUnavailable("versioned_html_required")
    return "https://arxiv.org/html/" + paper["id"] + version


def image_url(base, value):
    prefix = urllib.parse.urlsplit(base).path + "/"
    url = urllib.parse.urljoin(base, value)
    if not urllib.parse.urlsplit(url).path.startswith(prefix):
        url = urllib.parse.urljoin(base + "/", value)
    parsed = urllib.parse.urlsplit(url)
    suffix = parsed.path[len(prefix):] if parsed.path.startswith(prefix) else ""
    if parsed.scheme != "https" or parsed.netloc != "arxiv.org" or parsed.query or parsed.fragment:
        return None
    if not suffix or any(not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", part) or part in (".", "..") for part in suffix.split("/")):
        return None
    return url if re.search(r"\.(?:png|jpg|jpeg|svg)$", suffix, re.I) else None


class SameOrigin(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if new.scheme != "https" or new.netloc != old.netloc or new.path != old.path or new.query or new.fragment:
            raise SourceUnavailable("unexpected_source_redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_NEXT_REQUEST = 0.0


def download(url, limit, timeout):
    import time
    global _NEXT_REQUEST
    time.sleep(max(0, _NEXT_REQUEST - time.monotonic()))
    _NEXT_REQUEST = time.monotonic() + 3.1
    request = urllib.request.Request(url, headers={"User-Agent": "gnss-research-reading/3.0"})
    with urllib.request.build_opener(SameOrigin()).open(request, timeout=timeout) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise SourceUnavailable("source_too_large")
    return content


def licensed_source(paper, cache, timeout, max_characters):
    url = source_url(paper)
    path = cache / (paper["id"] + paper["version"] + ".html")
    content = path.read_bytes() if path.exists() else download(url, 5 * 1024 * 1024, timeout)
    source = parse_source(content, paper, max_characters)
    if not path.exists():
        path.write_bytes(content)
    abstract = cache / (paper["id"] + paper["version"] + "-abs.html")
    metadata = abstract.read_bytes() if abstract.exists() else download("https://arxiv.org/abs/" + paper["id"] + paper["version"], 1024 * 1024, timeout)
    parser = Tree()
    parser.feed(metadata.decode("utf-8"))
    licenses = []
    for node in parser.root.walk():
        value = node.attrs.get("href", "")
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme in ("https", "http") and parsed.netloc in ("arxiv.org", "creativecommons.org") and parsed.path.startswith("/licenses/") and not parsed.query and not parsed.fragment:
            licenses.append("https://" + parsed.netloc + parsed.path)
    if not licenses:
        raise SourceUnavailable("license_unverified")
    source["license_url"] = licenses[0]
    if not abstract.exists():
        abstract.write_bytes(metadata)
    return source


def mathml(node):
    if node.tag in ("annotation", "annotation-xml"):
        return ""
    children = "".join(mathml(child) if isinstance(child, Node) else html.escape(child) for child in node.children)
    if node.tag in ("math", "semantics"):
        return children
    if node.tag not in MATH_TAGS:
        raise ValueError("unsupported_source_math")
    attrs = ""
    from deep_reading import MATH_VARIANTS
    variant = node.attrs.get("mathvariant")
    if variant:
        if variant not in MATH_VARIANTS:
            raise ValueError("unsupported_source_math_variant")
        attrs = ' mathvariant="%s"' % variant
    if node.tag == "mspace" and node.attrs.get("width"):
        if not re.fullmatch(r"\d+(?:\.\d+)?em", node.attrs["width"]):
            raise ValueError("unsupported_source_math_spacing")
        attrs += ' width="%s"' % node.attrs["width"]
    return "<%s%s>%s</%s>" % (node.tag, attrs, children, node.tag)


def parse_source(content, paper, max_characters):
    base = source_url(paper)
    parser = Tree()
    parser.feed(content.decode("utf-8"))
    document = next((node for node in parser.root.walk() if "ltx_document" in node.attrs.get("class", "").split()), None)
    if document is None or "</article>" not in content.decode("utf-8").lower():
        raise SourceUnavailable("complete_html_unavailable")
    title = next((normalize(node.text(exclude_classes=("ltx_pubnotes", "ltx_role_note"))) for node in document.walk() if node.tag == "h1"), "")
    identities = [re.sub(r"\W", "", re.sub(r"(?<=\d)\s*[°∘]", " deg", value)).lower() for value in (title, paper["title_en"])]
    if identities[0] != identities[1]:
        raise SourceUnavailable("source_identity_mismatch")
    blocks, figures, equations = [], [], []
    for node in document.walk():
        classes = node.attrs.get("class", "").split()
        if node.tag in ("h1", "h2", "h3", "h4", "p", "figcaption", "table") and node.anchor():
            if node.tag == "table" and any(value.startswith("ltx_equation") for value in classes):
                continue
            text = normalize(node.text())
            if text and (node.tag != "p" or "ltx_p" in classes):
                blocks.append({"id": "S%d" % (len(blocks) + 1), "anchor": node.anchor(), "text": text})
        if node.tag == "figure" and "ltx_figure_panel" not in classes:
            caption = next((child for child in node.walk() if child.tag == "figcaption"), None)
            images = [child for child in node.walk() if child.tag == "img" or (child.tag == "object" and child.attrs.get("type") == "image/svg+xml")]
            number = re.search(r"(?:Figure|Fig\.)\s*(\d+)", caption.text() if caption else "", re.I)
            attribute = "data" if images and images[0].tag == "object" else "src"
            url = image_url(base, images[0].attrs.get(attribute, "")) if len(images) == 1 else None
            if caption and number and url and node.anchor():
                figures.append({"id": "F" + number.group(1), "number": int(number.group(1)), "anchor": node.anchor(), "src": url, "caption": normalize(caption.text())})
        if node.tag == "math" and node.attrs.get("display") == "block" and node.anchor():
            try:
                formula = checked_math(mathml(node))
            except ValueError:
                continue
            equations.append({"id": "M%d" % (len(equations) + 1), "anchor": node.anchor(), "mathml": formula, "text": node.attrs.get("alttext", normalize(node.text()))})
    main_sections = {block["anchor"].split(".")[0] for block in blocks if re.match(r"S\d", block["anchor"])}
    if len(main_sections) < 3 or sum(len(block["text"]) for block in blocks) < 4000:
        raise SourceUnavailable("insufficient_full_text")
    if sum(len(block["text"]) for block in blocks) > max_characters:
        raise SourceUnavailable("full_text_exceeds_configured_limit")
    raw_figures = sum(1 for node in document.walk() if node.tag == "figure" and "ltx_figure_panel" not in node.attrs.get("class", "").split() and len([child for child in node.walk() if child.tag == "img" or (child.tag == "object" and child.attrs.get("type") == "image/svg+xml")]) == 1)
    raw_equations = sum(node.tag == "math" and node.attrs.get("display") == "block" for node in document.walk())
    if raw_figures and len(figures) < min(2, raw_figures):
        raise SourceUnavailable("original_figures_unavailable")
    if raw_equations and not equations:
        raise SourceUnavailable("source_equations_unavailable")
    return {"url": base, "sha256": hashlib.sha256(content).hexdigest(), "blocks": blocks, "figures": figures, "equations": equations}


SVG_TAGS = {"svg", "g", "defs", "path", "use", "title", "desc", "metadata", "text", "tspan", "rect", "circle", "ellipse", "line", "polyline", "polygon", "clippath", "lineargradient", "radialgradient", "stop", "marker", "pattern", "mask", "symbol"}


def svg_dimensions(content):
    if re.search(br"<!(?:doctype|entity)\b", content, re.I):
        raise SourceUnavailable("unsupported_original_image")
    try:
        parser = Tree()
        parser.feed(content.decode("utf-8"))
    except UnicodeError:
        raise SourceUnavailable("unsupported_original_image")
    roots = [node for node in parser.root.children if isinstance(node, Node) and node.tag == "svg"]
    if len(roots) != 1:
        raise SourceUnavailable("unsupported_original_image")
    root = roots[0]
    count = 0
    for node in root.walk():
        count += 1
        if count > 200000 or node.tag not in SVG_TAGS:
            raise SourceUnavailable("unsupported_original_image")
        for key, value in node.attrs.items():
            local_clip = key == "clip-path" and re.fullmatch(r"url\(#[A-Za-z0-9_.:-]+\)", value)
            if key.lower().startswith("on") or ("url(" in value.lower() and not local_clip) or (key in ("href", "xlink:href") and not re.fullmatch(r"#[A-Za-z0-9_.:-]+", value)):
                raise SourceUnavailable("unsupported_original_image")
    if "viewbox" in root.attrs:
        try:
            values = [float(value) for value in root.attrs["viewbox"].replace(",", " ").split()]
            if len(values) == 4 and all(math.isfinite(value) for value in values) and values[2] > 0 and values[3] > 0:
                return round(values[2]), round(values[3])
        except ValueError:
            pass
    dimensions = []
    for key in ("width", "height"):
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:px|pt|mm|cm|in)?\s*", root.attrs.get(key, ""), re.I)
        if not match:
            raise SourceUnavailable("unsupported_original_image")
        dimensions.append(float(match.group(1)))
    if not all(math.isfinite(value) and value > 0 for value in dimensions):
        raise SourceUnavailable("unsupported_original_image")
    return tuple(round(value) for value in dimensions)


def image_dimensions(content):
    prefix = content[:4096].lstrip().lower()
    if prefix.startswith(b"<svg") or (prefix.startswith((b"<?xml", b"<!--", b"<!doctype")) and b"<svg" in prefix):
        return svg_dimensions(content)
    if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
        return struct.unpack(">II", content[16:24])
    if content.startswith(b"\xff\xd8"):
        index = 2
        while index + 4 <= len(content):
            if content[index] != 255:
                index += 1
                continue
            marker = content[index + 1]
            index += 2
            if marker in (0xd8, 0xd9) or 0xd0 <= marker <= 0xd7:
                continue
            length = struct.unpack(">H", content[index:index + 2])[0]
            if marker in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf) and length >= 7:
                height, width = struct.unpack(">HH", content[index + 3:index + 7])
                return width, height
            if length < 2:
                break
            index += length
    raise SourceUnavailable("unsupported_original_image")


def select_figures(source, timeout, cache_dir):
    figures = source["figures"]
    def priority(item):
        if re.search(r"framework|architecture|pipeline|overview of (?:the )?(?:proposed )?model", item["caption"], re.I):
            return 0
        if re.search(r"comparison|performance|result|fusion weight|error|accuracy", item["caption"], re.I):
            return 1
        return 2
    selected = sorted(figures, key=lambda item: (priority(item), item["number"]))[:3]
    output = []
    for item in selected:
        path = cache_dir / (hashlib.sha256(item["src"].encode()).hexdigest() + ".image")
        content = path.read_bytes() if path.exists() else download(item["src"], 8 * 1024 * 1024, timeout)
        width, height = image_dimensions(content)
        if not 1 <= width <= 8192 or not 1 <= height <= 8192:
            raise SourceUnavailable("unsupported_image_dimensions")
        if not path.exists():
            path.write_bytes(content)
        output.append(dict(item, width=width, height=height))
    if len(output) < min(2, len(figures)):
        raise SourceUnavailable("original_figures_unavailable")
    return output
