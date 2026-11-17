#!/usr/bin/env python3
"""Reject broken generated routes, missing fragments and unsafe deployment files."""

import argparse
import json
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

from build_site import Site
from deep_reading import equation_asset, validate_formula_asset
from radar_config import ROOT

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.ids = set()
        self.duplicates = []
        self.stack = []
        self.errors = []
        self.h1 = 0
        self.main = 0
        self.viewport = False
        self.title = False
        self.base = None
        self.paper_ids = []
        self.original_images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        if tag == "main":
            self.main += 1
        if tag == "title":
            self.title = True
        if tag == "meta" and attrs.get("name") == "viewport":
            self.viewport = True
        if tag == "base":
            self.base = attrs.get("href")
        if attrs.get("id"):
            value = attrs["id"]
            if value in self.ids:
                self.duplicates.append(value)
            self.ids.add(value)
        for key in ("href", "src", "action"):
            if key in attrs:
                self.links.append(attrs[key])
        if "data-paper-card" in attrs:
            self.paper_ids.append(attrs.get("data-id"))
        if tag == "img" and "data-original-image" in attrs:
            self.original_images.append(attrs)
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append("unexpected closing " + tag)
        else:
            self.stack.pop()


def check(root, public=False):
    root = Path(root).resolve()
    errors = []
    documents = {}
    for path in root.rglob("*.html"):
        relative = path.relative_to(root)
        if any(part.startswith(".") or part in ("node_modules", "_site") for part in relative.parts):
            continue
        doc = Document()
        doc.feed(path.read_text(encoding="utf-8"))
        doc.close()
        documents[path] = doc
        if doc.h1 != 1 or doc.main != 1 or not doc.viewport or not doc.title:
            errors.append("%s: missing/duplicate main, h1, title or viewport" % relative)
        if doc.stack or doc.errors or doc.duplicates:
            errors.append("%s: invalid structure %s %s %s" % (relative, doc.stack, doc.errors[:3], doc.duplicates))
        if len(doc.paper_ids) != len(set(doc.paper_ids)):
            errors.append("%s: duplicate paper cards" % relative)
    count = 0
    for path, doc in documents.items():
        base = root if doc.base else path.parent
        for url in doc.links:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme or parsed.netloc:
                if parsed.scheme not in ("https", "data", "mailto"):
                    errors.append("%s: unsafe link scheme %s" % (path.relative_to(root), url[:100]))
                continue
            target = (base / urllib.parse.unquote(parsed.path)).resolve() if parsed.path else path
            if target.is_dir():
                target = target / "index.html"
            if root != target and root not in target.parents:
                errors.append("%s: link escapes site: %s" % (path.relative_to(root), url))
                continue
            count += 1
            if not target.exists():
                errors.append("%s: missing target %s" % (path.relative_to(root), url))
            elif parsed.fragment and target in documents and urllib.parse.unquote(parsed.fragment) not in documents[target].ids:
                errors.append("%s: missing fragment %s" % (path.relative_to(root), url))
    site = Site()
    for paper in site.papers:
        path = root / "papers" / paper["slug"] / "index.html"
        if not path.exists():
            errors.append("missing paper page " + paper["id"])
        if paper["status"] == "deep":
            doc = documents.get(path)
            required = {"overview", "gap", "method", "equations", "experiments", "results", "limits", "transfer", "sources"}
            if not paper["deep_read"].get("format"):
                required.update(("figure-workflow", "figure-path", "figure-results"))
            required.update(item["id"] for item in paper["deep_read"]["equations"])
            originals = paper["deep_read"].get("original_figures", [])
            required.update(item["id"] for item in originals)
            if doc is None or not required.issubset(doc.ids):
                errors.append("incomplete full-text reading overlay: " + paper["id"])
            if doc is not None:
                expected = [(item["src"], str(item["width"]), str(item["height"]), item["alt"]) for item in originals]
                actual = [(item.get("src"), item.get("width"), item.get("height"), item.get("alt")) for item in doc.original_images]
                if sorted(expected) != sorted(actual) or any(item.get("referrerpolicy") != "no-referrer" for item in doc.original_images):
                    errors.append("incomplete or mismatched original figures: " + paper["id"])
    library = documents.get(root / "library" / "index.html")
    if library is None or set(library.paper_ids) != set(site.catalogue):
        errors.append("library is not the complete historical catalogue")
    for key in site.domains:
        doc = documents.get(root / "topics" / key / "index.html")
        expected = {paper["id"] for paper in site.papers if key in paper["domains"]}
        if doc is None or set(doc.paper_ids) != expected:
            errors.append("topic is not all-history: " + key)
    if public:
        formula_assets = set()
        for data in site.deep_reads.values():
            for equation in data["equations"]:
                for field in ("mathml", "mathml_second"):
                    if equation.get(field):
                        formula_assets.add(equation_asset(data, equation, field))
        if formula_assets:
            formula_assets.add("assets/deep-reading/LICENSE.txt")
        for path in root.rglob("*"):
            relative = path.relative_to(root).as_posix()
            if relative in formula_assets and path.suffix == ".svg":
                validate_formula_asset(path)
            if path.is_file() and path.name != ".nojekyll" and path.suffix not in (".html", ".css", ".js") and relative not in formula_assets:
                errors.append("unexpected deployment file: " + relative)
    if errors:
        print("site validation failed:", file=sys.stderr)
        for error in errors[:40]:
            print("  " + error, file=sys.stderr)
        return 1
    print("validated %d pages, %d local links/fragments, %d historical papers and %d full-history domains" % (
        len(documents), count, len(site.papers), len(site.domains)))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--public", action="store_true")
    args = parser.parse_args()
    return check(args.root, args.public)


if __name__ == "__main__":
    sys.exit(main())
