"""Publish explicitly approved Instagram image-post queue items via Meta Graph API.

Safety: disabled unless AUTO_PUBLISH_ENABLED=true; each item must have
approved=true, verified=true, an affiliate_url, and a public_image_url.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
QUEUE_PATH = os.getenv("CONTENT_QUEUE_PATH", "content_queue.json")
STATUS_PATH = os.getenv("PUBLISH_STATUS_PATH", "publish_status.json")


def request_json(url, data=None):
    payload = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=payload, method="POST" if payload else "GET")
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.loads(response.read().decode())


def main():
    if os.getenv("AUTO_PUBLISH_ENABLED", "").lower() != "true":
        print("Publishing disabled: set AUTO_PUBLISH_ENABLED=true to enable.")
        return 0

    user_id = os.getenv("META_IG_USER_ID")
    token = os.getenv("META_ACCESS_TOKEN")
    if not user_id or not token:
        print("Missing META_IG_USER_ID or META_ACCESS_TOKEN.")
        return 2
    if not os.path.exists(QUEUE_PATH):
        print(f"Queue not found: {QUEUE_PATH}")
        return 2

    with open(QUEUE_PATH, encoding="utf-8") as f:
        queue = json.load(f)
    with open(STATUS_PATH, encoding="utf-8") as f:
        status = json.load(f) if os.path.exists(STATUS_PATH) else {}

    items = queue.get("items", [])
    published = 0
    for index, item in enumerate(items):
        key = str(item.get("id") or item.get("affiliate_url") or index)
        if status.get(key, {}).get("status") == "published":
            continue
        if item.get("approved") is not True or item.get("verified") is not True:
            continue
        image_url = item.get("public_image_url")
        affiliate_url = item.get("affiliate_url")
        caption = item.get("caption")
        if not image_url or not affiliate_url or not caption:
            continue
        if not image_url.startswith("https://") or not affiliate_url.startswith("https://"):
            continue

        full_caption = f"{caption.strip()}\n\nShop here: {affiliate_url}"
        try:
            base = f"https://graph.facebook.com/{GRAPH_VERSION}/{user_id}"
            created = request_json(base + "/media", {
                "image_url": image_url,
                "caption": full_caption[:2200],
                "access_token": token,
            })
            creation_id = created.get("id")
            if not creation_id:
                raise RuntimeError(f"Media container response missing id: {created}")
            time.sleep(2)
            result = request_json(base + "/media_publish", {
                "creation_id": creation_id,
                "access_token": token,
            })
            status[key] = {"status": "published", "media_id": result.get("id")}
            published += 1
            print(f"Published queue item {key}: {result.get('id')}")
        except (urllib.error.URLError, RuntimeError, ValueError) as exc:
            status[key] = {"status": "failed", "error": str(exc)[:500]}
            print(f"Failed queue item {key}: {exc}", file=sys.stderr)

    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    print(f"Publishing run complete. Newly published: {published}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
