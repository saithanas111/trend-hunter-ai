"""Publish only fully verified, brand-distinct, reviewed true-3D CGI Instagram Reels.

Fail-closed safeguards:
- Publishing must be explicitly enabled.
- The live Instagram username must match META_IG_EXPECTED_USERNAME.
- Every item must pass queue_gate.py, including exact Daraz, trend, affiliate and video checks.
- This script publishes Reels only; it never substitutes an image or 2.5D zoom.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from queue_gate import validate_queue_payload

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
QUEUE_PATH = os.getenv("CONTENT_QUEUE_PATH", "content_queue.json")
STATUS_PATH = os.getenv("PUBLISH_STATUS_PATH", "publish_status.json")


def request_json(url, data=None):
    payload = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=payload, method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:1000]
        raise RuntimeError(f"Meta Graph API HTTP {exc.code}: {body}") from exc


def wait_for_video_container(container_id, token):
    url = (
        f"https://graph.facebook.com/{GRAPH_VERSION}/{container_id}?"
        + urllib.parse.urlencode({"fields": "status_code,status", "access_token": token})
    )
    for _ in range(60):
        state = request_json(url)
        status_code = str(state.get("status_code") or "").upper()
        if status_code == "FINISHED":
            return
        if status_code in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram video container failed: {state}")
        time.sleep(10)
    raise TimeoutError("Instagram Reel processing did not finish within 10 minutes.")


def main():
    if os.getenv("AUTO_PUBLISH_ENABLED", "").lower() != "true":
        print("Publishing disabled: AUTO_PUBLISH_ENABLED is not true.")
        return 0

    user_id = os.getenv("META_IG_USER_ID", "").strip()
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    expected_username = os.getenv("META_IG_EXPECTED_USERNAME", "").strip().lstrip("@").casefold()
    if not user_id or not token:
        print("Missing META_IG_USER_ID or META_ACCESS_TOKEN.", file=sys.stderr)
        return 2
    if not expected_username:
        print("Missing META_IG_EXPECTED_USERNAME; refusing to publish to an unconfirmed profile.", file=sys.stderr)
        return 2
    if not os.path.exists(QUEUE_PATH):
        print(f"Queue not found: {QUEUE_PATH}", file=sys.stderr)
        return 2

    with open(QUEUE_PATH, encoding="utf-8") as handle:
        queue = json.load(handle)
    ready, errors = validate_queue_payload(queue)
    if errors:
        for error in errors:
            print("PUBLISH BLOCKED:", error, file=sys.stderr)
        return 2
    if ready == 0:
        print("No fully verified, approved, true-3D CGI Reel is ready. Nothing was published.")
        return 0

    profile_url = (
        f"https://graph.facebook.com/{GRAPH_VERSION}/{user_id}?"
        + urllib.parse.urlencode({"fields": "id,username", "access_token": token})
    )
    profile = request_json(profile_url)
    actual_username = str(profile.get("username") or "").strip().lstrip("@").casefold()
    if str(profile.get("id") or "") != user_id or actual_username != expected_username:
        print(
            "PUBLISH BLOCKED: connected Instagram identity mismatch. "
            f"Expected @{expected_username}; Meta returned @{actual_username or 'unknown'}.",
            file=sys.stderr,
        )
        return 2

    if os.path.exists(STATUS_PATH):
        try:
            with open(STATUS_PATH, encoding="utf-8") as handle:
                status = json.load(handle)
            if not isinstance(status, dict):
                raise ValueError("Publishing status must be a JSON object.")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"Invalid publishing status file: {exc}", file=sys.stderr)
            return 2
    else:
        status = {}

    base = f"https://graph.facebook.com/{GRAPH_VERSION}/{user_id}"
    published = 0
    for index, item in enumerate(queue.get("items", [])):
        if item.get("approved") is not True or item.get("verified") is not True:
            continue
        key = str(item.get("id") or item.get("affiliate_url") or index)
        if status.get(key, {}).get("status") == "published":
            continue

        caption = str(item["instagram_caption"]).strip()
        full_caption = f"{caption}\n\nShop here: {item['affiliate_url']}"
        try:
            created = request_json(base + "/media", {
                "media_type": "REELS",
                "video_url": item["public_video_url"],
                "caption": full_caption[:2200],
                "share_to_feed": "true",
                "access_token": token,
            })
            container_id = created.get("id")
            if not container_id:
                raise RuntimeError(f"Reel container response missing id: {created}")
            wait_for_video_container(container_id, token)
            result = request_json(base + "/media_publish", {
                "creation_id": container_id,
                "access_token": token,
            })
            media_id = result.get("id")
            if not media_id:
                raise RuntimeError(f"Reel publish response missing media id: {result}")
            status[key] = {
                "status": "published",
                "media_id": media_id,
                "instagram_username": actual_username,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
            published += 1
            print(f"Published verified Reel {key}: {media_id}")
        except (urllib.error.URLError, RuntimeError, TimeoutError, ValueError) as exc:
            status[key] = {"status": "failed", "error": str(exc)[:500]}
            print(f"Failed Reel {key}: {exc}", file=sys.stderr)

    with open(STATUS_PATH, "w", encoding="utf-8") as handle:
        json.dump(status, handle, ensure_ascii=False, indent=2)
    print(f"Publishing run complete. Newly published Reels confirmed: {published}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
