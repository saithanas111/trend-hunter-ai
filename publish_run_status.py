"""Persist explicit outcomes for Meta publishing runs, including skipped runs."""

import json
import os
from datetime import datetime, timezone


def write_run_status(path, platform, status, reason, published_count=0, extra=None):
    """Write a reserved __run__ record while preserving per-product publish records."""
    records = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                records = json.load(handle)
            if not isinstance(records, dict):
                raise ValueError("Publishing status must be a JSON object.")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Could not read publishing status file {path}: {exc}") from exc

    run_record = {
        "platform": str(platform),
        "status": str(status),
        "reason": str(reason),
        "published_count": int(published_count),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    if isinstance(extra, dict) and extra:
        run_record["details"] = extra
    records["__run__"] = run_record

    temporary = str(path) + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)
    return run_record
