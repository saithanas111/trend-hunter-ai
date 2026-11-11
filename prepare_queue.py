import csv
import json
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path("daraz_candidates.json")
QUEUE_JSON = Path("content_queue.json")
QUEUE_CSV = Path("content_queue.csv")


def main():
    if not SOURCE.exists():
        raise SystemExit("daraz_candidates.json is missing; run main.py first.")
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    previous = {}
    if QUEUE_JSON.exists():
        try:
            old_items = json.loads(QUEUE_JSON.read_text(encoding="utf-8")).get("items", [])
            previous = {item.get("daraz_listing_url"): item for item in old_items if item.get("daraz_listing_url")}
        except Exception:
            previous = {}
    queue = []
    for number, product in enumerate(data.get("items", []), 1):
        copy = product.get("social_copy") or {}
        if not copy:
            continue
        old = previous.get(product.get("url", ""), {})
        queue.append({
            "id": str(number),
            "opportunity": number,
            "product": product.get("title", ""),
            "daraz_listing_url": product.get("url", ""),
            "search_query": product.get("search_query", ""),
            "listing_verification": product.get("verification", ""),
            "trend_evidence": product.get("trend_evidence", {}),
            "facebook_caption": copy.get("facebook_caption", ""),
            "instagram_caption": copy.get("instagram_caption", ""),
            "caption": copy.get("instagram_caption", ""),
            "reel_hook": copy.get("reel_hook", ""),
            "video_script": copy.get("video_script", ""),
            "hashtags": copy.get("hashtags", []),
            "affiliate_url": product.get("affiliate_url") or old.get("affiliate_url", ""),
            "public_image_url": product.get("public_image_url", ""),
            "public_video_url": product.get("public_video_url", ""),
            "video_cover_url": product.get("video_cover_url", ""),
            "verified": bool(old.get("verified", False)),
            "approved": bool(old.get("approved", False)),
            "affiliate_status": ("user_confirmed_affiliate_link" if product.get("affiliate_url") else old.get("affiliate_status", "manual_generation_required_no_supported_api_confirmed")),
            "publishing_status": old.get("publishing_status", "draft_not_published"),
            "approval_required": not bool(old.get("approved", False)),
        })
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(queue),
        "notice": "Drafts only. Every item starts unverified and unapproved. Publishing requires a verified product, approved post, affiliate URL, public image URL and enabled publishing secrets.",
        "items": queue,
    }
    QUEUE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["id", "opportunity", "product", "daraz_listing_url", "search_query",
              "listing_verification", "facebook_caption", "instagram_caption", "caption",
              "reel_hook", "video_script", "hashtags", "affiliate_url",
              "public_image_url", "public_video_url", "video_cover_url", "verified", "approved", "affiliate_status",
              "publishing_status", "approval_required"]
    with QUEUE_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in queue:
            row = dict(item)
            row["hashtags"] = " ".join(row["hashtags"]) if isinstance(row["hashtags"], list) else row["hashtags"]
            writer.writerow(row)
    print(f"Prepared {len(queue)} product-specific social drafts; all remain unverified and unapproved.")


if __name__ == "__main__":
    main()
