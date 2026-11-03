"""Validate Trend Hunter queue safety and publishing readiness without publishing."""
import json
from pathlib import Path

QUEUE = Path("content_queue.json")


def main():
    if not QUEUE.exists():
        raise SystemExit("FAIL: content_queue.json is missing.")
    payload = json.loads(QUEUE.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    errors = []
    ready = 0
    for i, item in enumerate(items, 1):
        if item.get("verified") is True and item.get("approved") is True:
            required = ("affiliate_url", "public_image_url", "caption")
            missing = [key for key in required if not item.get(key)]
            if missing:
                errors.append(f"Item {i}: approved/verified but missing {', '.join(missing)}")
            elif not str(item["affiliate_url"]).startswith("https://"):
                errors.append(f"Item {i}: affiliate_url must be HTTPS")
            elif not str(item["public_image_url"]).startswith("https://"):
                errors.append(f"Item {i}: public_image_url must be HTTPS")
            else:
                ready += 1
        else:
            if item.get("approved") is True and item.get("verified") is not True:
                errors.append(f"Item {i}: approved without verification")
    print(f"Queue items: {len(items)}")
    print(f"Publishing-ready items: {ready}")
    print(f"Blocked/unapproved items: {len(items) - ready}")
    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
