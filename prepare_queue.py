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
    queue = []
    for number, product in enumerate(data.get("items", []), 1):
        copy = product.get("social_copy") or {}
        if not copy:
            continue
        queue.append({
            "opportunity": number,
            "product": product.get("title", ""),
            "daraz_listing_url": product.get("url", ""),
            "search_query": product.get("search_query", ""),
            "listing_verification": product.get("verification", ""),
            "facebook_caption": copy.get("facebook_caption", ""),
            "instagram_caption": copy.get("instagram_caption", ""),
            "tiktok_hook": copy.get("tiktok_hook", ""),
            "video_script": copy.get("video_script", ""),
            "hashtags": copy.get("hashtags", []),
            "affiliate_url": "",
            "affiliate_status": "manual_generation_required_no_supported_api_confirmed",
            "publishing_status": "draft_not_published",
            "approval_required": True,
        })
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(queue),
        "notice": "Only products extracted from live Daraz search results are included. Listing details and affiliate eligibility still need verification. Affiliate link generation is not automated. Drafts are not published.",
        "items": queue,
    }
    QUEUE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["opportunity", "product", "daraz_listing_url", "search_query", "listing_verification", "facebook_caption", "instagram_caption", "tiktok_hook", "video_script", "hashtags", "affiliate_url", "affiliate_status", "publishing_status", "approval_required"]
    with QUEUE_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in queue:
            row = dict(item)
            row["hashtags"] = " ".join(row["hashtags"]) if isinstance(row["hashtags"], list) else row["hashtags"]
            writer.writerow(row)
    print(f"Prepared {len(queue)} product-specific social drafts from live Daraz listing candidates.")

if __name__ == "__main__":
    main()
