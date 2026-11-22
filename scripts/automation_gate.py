"""Gate daily retrieval on verified historical readings and explicitly approved skips."""

import argparse
import re
from pathlib import Path

from deep_reading import load_deep_reads
from radar_config import DATA, load_config, load_json
from reading_contract import skill


def automation_status(settings=None, directory=DATA, readings=None):
    settings = load_config()[2] if settings is None else settings
    config = settings.get("automation", {})
    path = directory / "backfill.json"
    manifest = load_json(path) if path.is_file() else {}
    required = manifest.get("paper_ids", []) if isinstance(manifest, dict) else []
    valid = isinstance(required, list) and bool(required) and all(
        isinstance(identity, str) and re.fullmatch(r"\d{4}\.\d{4,5}", identity) for identity in required
    ) and len(set(required)) == len(required)
    approved = manifest.get("approved_skips", {}) if valid else {}
    valid_skips = isinstance(approved, dict) and all(
        identity in required and reason in ("original_figure_rights_unconfirmed", "outside_editorial_scope")
        for identity, reason in approved.items()
    )
    if readings is None:
        readings = load_deep_reads(directory / "deep_reads")
    unpublished = set(required) - set(readings) if valid else set()
    skipped = {identity: approved[identity] for identity in sorted(unpublished) if identity in approved} if valid_skips else {}
    missing = sorted(unpublished - skipped.keys())
    digest = skill()[1]
    outdated = sorted(identity for identity in required if identity in readings and readings[identity].get("format") and
                      readings[identity].get("provenance", {}).get("skill_sha256") != digest) if valid else []
    ready = valid and valid_skips and not missing and not outdated
    valid_schedule = config.get("time") == "08:00" and config.get("timezone") == "Asia/Shanghai"
    enabled = config.get("enabled") is True and ready and valid_schedule
    reason = "enabled" if enabled else (
        "paused_for_backfill" if config.get("enabled") is not True else
        "invalid_schedule" if not valid_schedule else
        "backfill_manifest_required" if not valid else
        "invalid_backfill_skips" if not valid_skips else "historical_readings_incomplete"
    )
    return {
        "enabled": enabled, "requested_enabled": config.get("enabled") is True,
        "backfill_ready": ready, "total": len(required) if valid else 0,
        "completed": len(required) - len(unpublished) - len(outdated) if valid else 0,
        "skipped": skipped, "missing": missing, "outdated": outdated, "reason": reason,
        "time": "08:00", "timezone": "Asia/Shanghai",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--event", default="")
    args = parser.parse_args()
    status = automation_status()
    allowed = status["enabled"] and args.event in ("schedule", "workflow_dispatch")
    print("Daily automation: %s; historical readings %d/%d (%d explicitly skipped); schedule 08:00 Asia/Shanghai" % (
        status["reason"], status["completed"], status["total"], len(status["skipped"]),
    ))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write("allowed=%s\n" % str(allowed).lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
