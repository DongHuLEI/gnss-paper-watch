"""Run the project reading Skill with persistent budgets and publish-only-on-pass."""

import shutil
import subprocess
import tempfile
import time
import urllib.error
from collections import Counter
from pathlib import Path

from deep_reading import equation_asset, validate_formula_asset
from paper_source import SourceUnavailable, licensed_source, select_figures
from radar_config import DATA, ROOT, load_json, utc_timestamp, write_json
from reading_contract import skill, validate_saved

STATUS_LABELS = {
    "complete": "图文精读已生成，待人工核验", "missing_key": "待处理：未配置 API 密钥",
    "daily_token_limit": "待处理：当日 token 预算不足", "daily_paper_limit": "待处理：当日模型请求额度已用完",
    "chat_request_limit": "待处理：当日重试请求额度已用完", "source_unavailable": "待处理：未取得可完整核读的版本化全文",
    "source_throttled": "待处理：原文来源限流，后续补跑", "full_text_exceeds_configured_limit": "待处理：全文过长，需调整读取预算或人工核读",
    "original_figures_unavailable": "待处理：原图获取不完整", "invalid_or_ungrounded_reading": "待处理：结构、证据或输出完整性未通过检查",
    "formula_rendering_failed": "待处理：公式排版未通过检查", "invalid_key": "待处理：API 认证失败",
    "insufficient_balance": "待处理：API 余额不足", "verified_vision_model_required": "待处理：需使用已核对的视觉模型",
    "license_unverified": "待处理：未能确认原文许可", "source_equations_unavailable": "待处理：原文公式无法安全提取",
    "run_time_limit": "待处理：本次运行时间不足，留待后续补跑", "disabled": "待处理：AI 已停用",
}


def label(value):
    return STATUS_LABELS.get(value, "待处理：全文、原图或质量检查尚未完成")


def publish_reading(data, directory=DATA, assets_root=ROOT):
    validate_saved(data)
    cache = ROOT / ".cache" / "paper-reading"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(cache)) as temporary:
        stage = Path(temporary)
        source = stage / "reading.json"
        write_json(source, data)
        try:
            subprocess.check_call(["node", str(ROOT / "scripts/render_equations.cjs"), "--source", str(source), "--output", str(stage / "assets")], cwd=str(ROOT))
            for equation in data["equations"]:
                asset = Path(equation_asset(data, equation, "mathml"))
                validate_formula_asset(stage / "assets" / asset.relative_to("assets/deep-reading"))
        except (OSError, ValueError, subprocess.CalledProcessError):
            raise SourceUnavailable("formula_rendering_failed")
        destination = assets_root / "assets/deep-reading" / data["paper_id"]
        destination.mkdir(parents=True, exist_ok=True)
        for image in (stage / "assets" / data["paper_id"]).glob("*.svg"):
            shutil.copyfile(str(image), str(destination / image.name))
        write_json(directory / "deep_reads" / (data["paper_id"] + ".json"), data)


def enrich_full_readings(papers, client, profile, editions, directory=DATA, deadline=None):
    body, digest = skill()
    queue_path = directory / "reading_queue.json"
    queue = load_json(queue_path) if queue_path.exists() else {"skill": "paper-deep-reading", "papers": {}}
    cache = ROOT / ".cache" / "paper-reading"
    cache.mkdir(parents=True, exist_ok=True)
    candidates = {}
    for view in editions:
        for paper in view["papers"]:
            if paper.get("auto") and paper["id"] in queue["papers"] and paper["id"] not in candidates:
                candidates[paper["id"]] = paper
    for paper in papers:
        if paper.get("auto"):
            candidates[paper["id"]] = paper
    current = {paper["id"] for paper in papers}
    ordered = sorted(candidates.values(), key=lambda item: (item["id"] not in current, -item.get("score", 0), item["date"]))
    completed = {path.stem for path in (directory / "deep_reads").glob("*.json")}
    throttled = False
    for paper in ordered:
        identity = paper["id"]
        if identity in completed:
            continue
        previous = queue["papers"].get(identity, {})
        record = dict(previous, paper_id=identity, skill_sha256=digest, checked_at=utc_timestamp())
        record.setdefault("queued_at", utc_timestamp())
        reason = None
        if not client.available:
            reason = client.state
        elif deadline is not None and time.monotonic() + client.config["request_timeout"] * 7 + 20 > deadline:
            reason = "run_time_limit"
        elif throttled:
            reason = "source_throttled"
        elif client.ledger["successes"]["chat"] >= client.config["daily_paper_limit"]:
            reason = "daily_paper_limit"
        elif client.ledger["accounted_tokens"] + len(body.encode("utf-8")) + client.config["full_reading_completion_tokens"] > client.config["daily_token_limit"]:
            reason = "daily_token_limit"
        if reason is None:
            try:
                source = licensed_source(paper, cache, client.config["request_timeout"], client.config["full_reading_character_limit"])
                figures = select_figures(source, client.config["request_timeout"], cache)
                result, reason = client.analyze_full_reading(paper, profile, source, figures)
                if result:
                    publish_reading(result, directory)
                    reason = "complete"
                    record["source_sha256"] = source["sha256"]
                    record["completed_at"] = utc_timestamp()
            except urllib.error.HTTPError as error:
                throttled = error.code == 429
                reason = "source_throttled" if throttled else "source_unavailable"
            except SourceUnavailable as error:
                reason = str(error) if str(error) in STATUS_LABELS else "source_unavailable"
            except (OSError, ValueError, KeyError, TypeError):
                reason = "source_unavailable"
        record["status"] = reason
        queue["papers"][identity] = record
        write_json(queue_path, queue)
        print("full reading %s: %s" % (identity, reason), flush=True)
    queue["updated_at"] = utc_timestamp()
    queue["skill_sha256"] = digest
    write_json(queue_path, queue)
    counts = Counter(item["status"] for item in queue["papers"].values() if item["paper_id"] not in completed or item["status"] == "complete")
    return {"skill": "paper-deep-reading", "skill_sha256": digest, "states": dict(counts), "pending": sum(count for state, count in counts.items() if state != "complete")}
