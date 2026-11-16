import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BEIJING = dt.timezone(dt.timedelta(hours=8))


def load_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_config():
    taxonomy = load_json(DATA / "domains.json")
    settings = load_json(DATA / "settings.json")
    return taxonomy["domains"], taxonomy.get("lenses", {}), settings


def beijing_now():
    return dt.datetime.now(BEIJING)


def utc_timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def matches(value, term):
    pattern = r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])"
    return bool(re.search(pattern, value.lower()))


def classify(title, abstract, domains, lenses):
    text = (title + " " + abstract).lower()
    scores = {}
    terms = {}
    for key, domain in domains.items():
        anchors = domain.get("anchors", [])
        if not any(matches(text, term) for term in anchors):
            continue
        hits = [term for term in domain.get("terms", []) if matches(text, term)]
        if not hits:
            continue
        if key == "gnss" and not any(matches(text, term) for term in (
            "positioning", "navigation", "ambiguity", "rtk", "ppp", "localization"
        )):
            continue
        if key == "ml" and not any(matches(text, term) for term in (
            "learning", "forecasting", "prediction", "neural", "transformer", "foundation model"
        )):
            continue
        title_hits = sum(matches(title, term) for term in anchors + hits)
        score = min(100, 24 + len(hits) * 7 + min(title_hits, 3) * 8)
        scores[key] = score
        terms[key] = hits
    ranked = sorted(scores, key=lambda key: -scores[key])
    return {
        "domain": ranked[0] if ranked else None,
        "domains": ranked,
        "domain_scores": scores,
        "matched_terms": terms.get(ranked[0], []) if ranked else [],
        "score": scores[ranked[0]] if ranked else 0,
        "lenses": [key for key, lens in lenses.items() if any(matches(text, term) for term in lens["terms"])],
    }


def load_editions(directory=None):
    directory = Path(directory) if directory else DATA / "editions"
    editions = []
    for path in sorted(directory.glob("*.json")):
        data = load_json(path)
        data["_path"] = path
        editions.append(data)
    return sorted(editions, key=lambda item: item["edition"]["date"], reverse=True)


def known_ids(editions):
    return {re.sub(r"v\d+$", "", paper["id"]) for view in editions for paper in view.get("papers", [])}


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    temporary.replace(path)
