"""Allowlist for complete, unaltered image objects from licensed arXiv PDFs."""

import hashlib
import re


SOURCE_TYPE = "licensed_arxiv_pdf"
LICENSES = {
    "by": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "by-nc-nd": ("CC BY-NC-ND 4.0", "https://creativecommons.org/licenses/by-nc-nd/4.0/"),
}
# Each entry binds the official version and license to reviewed image objects only.
# Figure rows: PDF page, extension, natural width, natural height, asset SHA-256.
APPROVED = {
    ("2606.29644", "v1"): (
        "by", "40a8406d70ace911ce3e0bcc82e53f28c297061d147d9bc166b51aefaebefc26", 40,
        "Stephen Tete、Carl Shneider、Maxime Cordy、Claudio Cesaroni、Andreas Hein、Vasily Petrov",
        {
            3: (15, "png", 1208, 655, "78bdbf1a5cb3d4b5840973129f3805988a65ad73de0fea22c61de80351b12c8d"),
            6: (22, "jpg", 1299, 711, "be3458117dc3ff761834535addfb205a9f90333a46126b0b7e53af5e2a3acb22"),
            7: (24, "jpg", 1299, 711, "a3e1622f0a71b5d278b6484ebc71fde3ac567aa97ce31409c2831a5755fab02c"),
        },
    ),
    ("2608.25764", "v1"): (
        "by-nc-nd", "8ca5874caafca852b48d4c3699ff6d2a15681cb7e86c29c62add5123482bcab1", 33,
        "Daria Kotova、Luca Spogli、Yaqi Jin、Wojciech Miloch",
        {
            2: (7, "png", 1253, 1427, "5cbd1cb11b3b55e18f486676ff5af799844445c65141f4335cbba44e4b12f5b7"),
            6: (13, "png", 1600, 2000, "3b347c336e7ff5cc76a759ca6db52701ab30a1b488cdf2312098340fcc34cc6f"),
            7: (14, "png", 1600, 2000, "cdd663bf59f4a37b3ac9983b4bba970a5baa79e629cf95d64695d879b5adcac6"),
        },
    ),
}


def is_pdf(data):
    return data.get("source_type") == SOURCE_TYPE


def versioned_abs(data):
    return "https://arxiv.org/abs/" + data["paper_id"] + data["source_version"]


def asset_path(data, number, extension):
    return "assets/deep-reading/%s/original-fig-%d.%s" % (data["paper_id"], number, extension)


def original_paths(data):
    return [item["src"] for item in data["original_figures"]] if is_pdf(data) else []


def image_href(data, item):
    return ("../../" if is_pdf(data) else "") + item["src"]


def validate_source(data):
    approved = APPROVED.get((data["paper_id"], data["source_version"]))
    if not approved:
        raise ValueError("unapproved licensed PDF version")
    license_key, sha, page_count, authors, figures = approved
    provenance = data.get("provenance", {})
    if (data.get("format") != "paper-deep-reading-v1" or provenance.get("generation_mode") != "assistant_backfill"
            or data.get("source_url") != "https://arxiv.org/pdf/" + data["paper_id"] + data["source_version"]
            or provenance.get("license_url") != LICENSES[license_key][1]
            or provenance.get("license_evidence_url") != versioned_abs(data)
            or provenance.get("source_sha256") != sha or data.get("original_figure_credit") != authors):
        raise ValueError("unverified licensed PDF provenance")
    if license_key == "by-nc-nd" and provenance.get("reuse_purpose") != "noncommercial":
        raise ValueError("licensed PDF requires noncommercial reuse")
    for reference in data["references"].values():
        match = re.fullmatch(r"page=([1-9]\d{0,2})", reference["anchor"])
        if not match or int(match[1]) > page_count:
            raise ValueError("invalid licensed PDF page")
    if len(data["original_figures"]) != len(figures) or {item["number"] for item in data["original_figures"]} != set(figures):
        raise ValueError("incomplete set of approved original figures")
    if not 2 <= len(data["equations"]) <= 5 or any(not item.get("mathml") or not item.get("refs") or any(key not in data["references"] for key in item["refs"]) for item in data["equations"]):
        raise ValueError("missing licensed PDF equation references")
    return figures


def validate_image(data, item, root, figures=None):
    number = item["number"]
    page, extension, width, height, sha = (figures if figures is not None else validate_source(data))[number]
    if (item["src"] != asset_path(data, number, extension)
            or (item["width"], item["height"]) != (width, height)
            or item.get("modified") is not False or item.get("asset_sha256") != sha
            or data["references"][item["reference"]]["anchor"] != "page=%d" % page
            or not item.get("caption", "").strip() or not 2 <= len(item["reading_steps"]) <= 4):
        raise ValueError("invalid licensed PDF original figure")
    asset = root / item["src"]
    if not asset.is_file() or hashlib.sha256(asset.read_bytes()).hexdigest() != sha:
        raise ValueError("licensed PDF original figure hash mismatch: " + str(asset))


def license_credit(data):
    key = APPROVED[(data["paper_id"], data["source_version"])][0]
    name, url = LICENSES[key]
    purpose = "；本站仅作非商业转载" if key == "by-nc-nd" else ""
    return name, url, purpose
