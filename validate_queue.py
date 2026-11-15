"""Validate Trend Hunter queue safety and publishing readiness without publishing."""

import json
from pathlib import Path

from queue_gate import validate_queue_payload

QUEUE = Path("content_queue.json")


def main():
    if not QUEUE.exists():
        raise SystemExit("FAIL: content_queue.json is missing.")
    payload = json.loads(QUEUE.read_text(encoding="utf-8"))
    ready, errors = validate_queue_payload(payload)
    items = payload.get("items", [])
    print(f"Queue items: {len(items)}")
    print(f"Strictly publishing-ready true-3D CGI items: {ready}")
    print(f"Draft/unapproved items: {len(items) - ready}")
    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
