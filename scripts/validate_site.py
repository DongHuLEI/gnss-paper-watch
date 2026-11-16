#!/usr/bin/env python3
"""Reject broken generated routes, missing fragments and unsafe deployment files."""

import argparse
import json
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

from build_site import Site
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
        if not (root / "papers" / paper["slug"] / "index.html").exists():
            errors.append("missing paper page " + paper["id"])
    library = documents.get(root / "library" / "index.html")
    if library is None or set(library.paper_ids) != set(site.catalogue):
        errors.append("library is not the complete historical catalogue")
    for key in site.domains:
        doc = documents.get(root / "topics" / key / "index.html")
        expected = {paper["id"] for paper in site.papers if key in paper["domains"]}
        if doc is None or set(doc.paper_ids) != expected:
            errors.append("topic is not all-history: " + key)
    if public:
        for path in root.rglob("*"):
            if path.is_file() and path.name != ".nojekyll" and path.suffix not in (".html", ".css", ".js"):
                errors.append("unexpected deployment file: " + str(path.relative_to(root)))
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
