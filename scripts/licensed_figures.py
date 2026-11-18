"""Allowlist for complete, unaltered figures from licensed arXiv PDFs."""

import hashlib
import re


SOURCE_TYPE = "licensed_arxiv_pdf"
LICENSES = {
    "by": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "by-nc-nd": ("CC BY-NC-ND 4.0", "https://creativecommons.org/licenses/by-nc-nd/4.0/"),
}
# Each entry binds the official version and license to individually verified complete figures.
# Figure rows: PDF page, extension, natural width, natural height, asset SHA-256.
APPROVED = {
    ("2611.00316", "v1"): (
        "by", "5c243e2f0090f0092ec03d26b3b25625e489d464267ea547a7d942133c3ae39e", 15,
        "Zakaria El Mrabet、Prakash Ranganathan",
        {
            4: (5, "png", 4469, 1809, "2e3cafa298e8d60936f366ed67a8e91d81e4d9408fc83da7aac64d5551be9797"),
            5: (6, "png", 4266, 2538, "697f4c73ece7ce4b660cba5bd3106b23257c28f854f7dc2e594144a74ff766f2"),
        },
    ),
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
    ("2611.14250", "v1"): (
        "by-nc-nd", "63ee1f6183a0d5b49ee962af940adef4593fd1f2a94b230c214f4ff52c454f9b", 6,
        "Paolo Tosi、Ossi Kaltiokallio、Marcus Henninger、Silvio Mandelli、Mikko Valkama",
        {
            2: (3, "png", 1476, 684, "8e44f4d79d4a3985dc79254b1493324d18ca1debaff60da230cad6274c4e95dd"),
            4: (6, "png", 1416, 840, "3f5fef4b90dd16cbc5e3b6550f9d7d20677e6c45c8c20bfa13161c2291628042"),
        },
    ),
    ("2611.14397", "v1"): (
        "by", "9bde2156f6456a90b2322a92de4c504013912e3e212df7b0686054cbb8089129", 61,
        "Ziqing Xu、Hancheng Min、Lachlan Ewen MacDonald、Salma Tarmoun、Enrique Mallada、Weijie Su、Rene Vidal",
        {
            1: (9, "png", 10835, 2847, "5fc41fee42c9e6fd0070a6dbb9aa557ab42b372d6792bb9986db4bdc4da5925b"),
            3: (50, "png", 6466, 5344, "b552f634c3891e94099fb52f5145c6e72161ea400d44ec13835e87e9f9cc17a0"),
            4: (50, "png", 10833, 2979, "19a7d9903f817302885ece0d0cdc1a61eb8323912dc26c23be3910bba6d5398f"),
        },
    ),
    ("2611.12806", "v1"): (
        "by", "5f0c52f41165e1f370a7da775e0659e7d41a77f4333a8c835558300993e75ba3", 27,
        "Bing Han、Yichuan Peng、Haoyu Dong、Yuanmeng Hu、Yongyi Jia、Fangjing Wang、Kecheng Zheng、Yiming Zhang、Yanhong Zeng、Xiaoqing Zhang、Chen Song、Rundong Zou、Anqi Dong、Yuan Guan、Ka Leong Cheng、Xing Zhu、Yujun Shen、Nan Xue、Wei Ning",
        {
            3: (5, "svg", 956, 395, "f81546c6fc2e6f4d109483aa92bbc4ad3072219ea11ddb0b1c68b6d4b39ecb8b"),
            8: (11, "svg", 2973, 939, "2e6200c7ad1eae1ef1cd741ccf0fbf6924065512f1a08bd76d506655138aa17b"),
            14: (21, "jpg", 1800, 201, "4f4a4aa9966e460af19a48e7adb38ad52a256fd10deae07cb71e550761b68840"),
        },
    ),
}
FIGURE_REGION_RENDERS = {("2611.14250", "v1", 2), ("2611.14250", "v1", 4)}

FIGURE_FORM_SVGS = {("2611.12806", "v1", 3), ("2611.12806", "v1", 8)}
CAPTION_SHA256 = {
    ("2611.12806", "v1", 3): "28fd44d5b96b7470840ccb894c6d354df34cf8cd26e55393549589c79bba6321",
    ("2611.12806", "v1", 8): "4c358cd9abe8722e019bd8c0ffd63d514ac0b2ae2a2a2b0cc2b3358290815958",
    ("2611.12806", "v1", 14): "708b930fc95e76cdf9683879fc54946e8e6938dd0e805d442fda5b2a98075198",
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
    caption_hash = CAPTION_SHA256.get((data["paper_id"], data["source_version"], number))
    if caption_hash and hashlib.sha256(item.get("caption", "").encode("utf-8")).hexdigest() != caption_hash:
        raise ValueError("licensed PDF original caption hash mismatch")
    if (item.get("rendering") != figure_rendering(data, number)
            or any(type(item[k]) is not int or not 1 <= item[k] <= 12000 for k in ("width", "height"))
            or item["src"] != asset_path(data, number, extension)
            or (item["width"], item["height"]) != (width, height)
            or item.get("modified") is not False or item.get("asset_sha256") != sha
            or data["references"][item["reference"]]["anchor"] != "page=%d" % page
            or not item.get("caption", "").strip() or not 2 <= len(item["reading_steps"]) <= 4):
        raise ValueError("invalid licensed PDF original figure")
    asset = root / item["src"]
    if not asset.is_file() or hashlib.sha256(asset.read_bytes()).hexdigest() != sha:
        raise ValueError("licensed PDF original figure hash mismatch: " + str(asset))


def figure_rendering(data, number):
    if (data["paper_id"], data["source_version"], number) in FIGURE_FORM_SVGS:
        return "complete_figure_pdf_svg"
    if (data["paper_id"], data["source_version"], number) in FIGURE_REGION_RENDERS:
        return "complete_figure_pdf_region"
    return None


def license_credit(data):
    key = APPROVED[(data["paper_id"], data["source_version"])][0]
    name, url = LICENSES[key]
    purpose = "；本站仅作非商业转载" if key == "by-nc-nd" else ""
    return name, url, purpose
