"""Fail-closed publisher for verified vertical CGI product videos to the connected Facebook Page."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

from queue_gate import validate_queue_payload
from publish_limits import can_publish, current_local_day, load_daily_log, record_publish, save_daily_log
from publish_run_status import write_run_status

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
EXPECTED_PAGE_ID = "1212885835249403"
EXPECTED_PAGE_NAME = "trending finds"
QUEUE_PATH = os.getenv("CONTENT_QUEUE_PATH", "content_queue.json")
STATUS_PATH = os.getenv("FACEBOOK_PUBLISH_STATUS_PATH", "facebook_publish_status.json")


def request_json(url, data=None):
    payload = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=payload, method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:1000]
        raise RuntimeError(f"Meta Graph API HTTP {exc.code}: {body}") from exc


def validate_target_page(configured_page_id, page_info):
    """Fail closed unless the configured and live Page identity match the connected Page."""
    configured = str(configured_page_id or "").strip()
    if configured != EXPECTED_PAGE_ID:
        raise RuntimeError(
            f"Configured Facebook Page ID must be {EXPECTED_PAGE_ID}; received {configured or 'empty'}."
        )
    actual_id = str((page_info or {}).get("id") or "").strip()
    actual_name = str((page_info or {}).get("name") or "").strip().casefold()
    if actual_id != EXPECTED_PAGE_ID:
        raise RuntimeError(
            f"Connected Facebook Page ID mismatch: expected {EXPECTED_PAGE_ID}, received {actual_id or 'unknown'}."
        )
    if actual_name != EXPECTED_PAGE_NAME:
        raise RuntimeError(
            f"Connected Facebook Page name mismatch: expected Trending Finds, received {actual_name or 'unknown'}."
        )
    return EXPECTED_PAGE_ID


def item_key(item, index=0):
    """Use a stable listing identity, never a queue position, to prevent duplicate posts."""
    for field in ("daraz_listing_url", "affiliate_url", "id"):
        value = str(item.get(field) or "").strip()
        if value:
            return value
    return str(index)


def format_caption(item):
    caption = str(item.get("facebook_caption") or "").strip()
    affiliate_url = str(item.get("affiliate_url") or "").strip()
    if affiliate_url and affiliate_url not in caption:
        caption = f"{caption}\n\nShop here: {affiliate_url}".strip()
    return caption[:10000]


def validate_video_url(video_url):
    parsed = urlparse(str(video_url or "").strip())
    if parsed.scheme != "https" or not (parsed.hostname or ""):
        raise RuntimeError("Facebook video URL must be a public HTTPS URL.")
    if not parsed.path.lower().endswith((".mp4", ".mov")):
        raise RuntimeError("Facebook publishing requires a public MP4 or MOV video URL.")
    return video_url


def publish_video(page_id, token, item):
    video_url = validate_video_url(item.get("public_video_url"))
    caption = format_caption(item)
    if not caption or "comment order" not in caption.casefold():
        raise RuntimeError("Facebook caption is missing the required Comment ORDER CTA.")
    endpoint = f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/videos"
    return request_json(endpoint, {
        "file_url": video_url,
        "title": str(item.get("product") or "Product video")[:100],
        "description": caption,
        "published": "true",
        "access_token": token,
    })


def main():
    if os.getenv("FACEBOOK_AUTO_PUBLISH_ENABLED", "").strip().lower() != "true":
        write_run_status(STATUS_PATH, "facebook", "skipped", "FACEBOOK_AUTO_PUBLISH_ENABLED is not true.", extra={"page_id": EXPECTED_PAGE_ID})
        print("Facebook publishing disabled: FACEBOOK_AUTO_PUBLISH_ENABLED is not true.")
        return 0

    page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
    token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
    if not page_id or not token:
        reason = "Missing FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN."
        write_run_status(STATUS_PATH, "facebook", "blocked", reason, extra={"page_id": page_id or EXPECTED_PAGE_ID})
        print("PUBLISH BLOCKED:", reason, file=sys.stderr)
        return 2
    try:
        if page_id != EXPECTED_PAGE_ID:
            raise RuntimeError("Configured Page ID does not match the connected Trending Finds Page.")
        if not os.path.exists(QUEUE_PATH):
            raise RuntimeError(f"Queue not found: {QUEUE_PATH}")
        with open(QUEUE_PATH, encoding="utf-8") as handle:
            queue = json.load(handle)
        ready, errors = validate_queue_payload(queue)
        if errors:
            write_run_status(STATUS_PATH, "facebook", "blocked", "Queue gate rejected one or more items.", extra={"gate_errors": errors, "page_id": page_id})
            for error in errors:
                print("PUBLISH BLOCKED:", error, file=sys.stderr)
            return 2
        if ready == 0:
            reason = "No fully verified, approved, true-3D CGI product video is ready for Facebook."
            write_run_status(STATUS_PATH, "facebook", "skipped", reason, extra={"page_id": page_id})
            print(reason + " Nothing was published.")
            return 0

        page_url = (
            f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}?"
            + urllib.parse.urlencode({"fields": "id,name", "access_token": token})
        )
        page_info = request_json(page_url)
        validate_target_page(page_id, page_info)

        if os.path.exists(STATUS_PATH):
            try:
                with open(STATUS_PATH, encoding="utf-8") as handle:
                    status = json.load(handle)
                if not isinstance(status, dict):
                    raise ValueError("Facebook publishing status must be a JSON object.")
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                raise RuntimeError(f"Invalid Facebook publishing status file: {exc}") from exc
        else:
            status = {}

        try:
            daily_log = load_daily_log()
        except RuntimeError as exc:
            raise RuntimeError(f"Daily publishing log unavailable: {exc}") from exc
        today = current_local_day()

        published = 0
        failures = 0
        for index, item in enumerate(queue.get("items", [])):
            if item.get("approved") is not True or item.get("verified") is not True:
                continue
            key = item_key(item, index)
            if status.get(key, {}).get("status") == "published":
                continue
            allowed, reason = can_publish(daily_log, key, "facebook", item.get("brand"), today=today)
            if not allowed:
                print(f"Skipped Facebook item {key}: {reason}")
                continue
            try:
                created = publish_video(page_id, token, item)
                video_id = str(created.get("id") or "").strip()
                if not video_id:
                    raise RuntimeError(f"Facebook video response missing id: {created}")
                details = {
                    "status": "published",
                    "video_id": video_id,
                    "page_id": page_id,
                    "page_name": page_info.get("name"),
                    "published_at": datetime.now(timezone.utc).isoformat(),
                }
                status[key] = details
                record_publish(daily_log, key, "facebook", item, details, today=today)
                save_daily_log(daily_log)
                published += 1
                print(f"Published verified Facebook Page video {key}: {video_id}")
            except (urllib.error.URLError, RuntimeError, TimeoutError, ValueError) as exc:
                status[key] = {"status": "failed", "error": str(exc)[:500]}
                failures += 1
                print(f"Failed Facebook Page video {key}: {exc}", file=sys.stderr)

        with open(STATUS_PATH, "w", encoding="utf-8") as handle:
            json.dump(status, handle, ensure_ascii=False, indent=2)
        save_daily_log(daily_log)
        run_state = "partial_failure" if failures else "completed"
        run_reason = "One or more Facebook Page video publish attempts failed." if failures else "Facebook publishing run completed; only Meta-confirmed video IDs are recorded."
        write_run_status(STATUS_PATH, "facebook", run_state, run_reason, published_count=published, extra={"failed_attempts": failures, "page_id": page_id, "page_name": page_info.get("name")})
        print(f"Facebook publishing run complete. Newly published Page videos confirmed: {published}; failed attempts: {failures}")
        return 1 if failures else 0
    except (urllib.error.URLError, RuntimeError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        write_run_status(STATUS_PATH, "facebook", "blocked", str(exc), extra={"page_id": page_id or EXPECTED_PAGE_ID})
        print(f"PUBLISH BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
