import csv
import json
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path("daraz_candidates.json")
QUEUE_JSON = Path("content_queue.json")
QUEUE_CSV = Path("content_queue.csv")


def normalize_trend_evidence(raw):
    if not isinstance(raw, dict):
        return {}
    return {
        "title": raw.get("title") or raw.get("signal_title") or "",
        "source_name": raw.get("source_name") or raw.get("source") or "",
        "source_url": raw.get("source_url") or raw.get("url") or "",
        "observed_at": raw.get("observed_at") or raw.get("timestamp") or "",
        "metric": raw.get("metric") or raw.get("views") or "",
    }


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
        trend_evidence = normalize_trend_evidence(
            product.get("trend_evidence") or old.get("trend_evidence")
        )
        video_url = product.get("public_video_url") or old.get("public_video_url", "")
        queue.append({
            "id": str(number),
            "opportunity": number,
            "product": product.get("title", ""),
            "brand": product.get("brand") or old.get("brand", ""),
            "daraz_listing_url": product.get("url", ""),
            "search_query": product.get("search_query", ""),
            "listing_verification": product.get("verification", ""),
            "exact_variant": product.get("exact_variant") or old.get("exact_variant", ""),
            "exact_match_confirmed": bool(product.get("exact_match_confirmed", old.get("exact_match_confirmed", False))),
            "current_price": product.get("current_price") or old.get("current_price", ""),
            "sold_count": product.get("sold_count") or old.get("sold_count", ""),
            "rating": product.get("rating") or old.get("rating", ""),
            "stock_status": product.get("stock_status") or old.get("stock_status", ""),
            "seller": product.get("seller") or old.get("seller", ""),
            "seller_listing_consistent": bool(product.get("seller_listing_consistent", old.get("seller_listing_consistent", False))),
            "listing_verified_at": product.get("listing_verified_at") or old.get("listing_verified_at", ""),
            "trend_evidence": trend_evidence,
            "facebook_caption": copy.get("facebook_caption", ""),
            "instagram_caption": copy.get("instagram_caption", ""),
            "caption": copy.get("instagram_caption", ""),
            "reel_hook": copy.get("reel_hook", ""),
            "video_script": copy.get("video_script", ""),
            "hashtags": copy.get("hashtags", []),
            "affiliate_url": product.get("affiliate_url") or old.get("affiliate_url", ""),
            "affiliate_link_verified": bool(product.get("affiliate_link_verified", old.get("affiliate_link_verified", False))),
            "affiliate_link_verified_at": product.get("affiliate_link_verified_at") or old.get("affiliate_link_verified_at", ""),
            "public_image_url": product.get("public_image_url", ""),
            "public_video_url": video_url,
            "video_cover_url": product.get("video_cover_url") or old.get("video_cover_url", ""),
            "video_type": product.get("video_type") or old.get("video_type") or ("2.5d_image_motion" if video_url else "not_generated"),
            "video_reviewed": bool(product.get("video_reviewed", old.get("video_reviewed", False))),
            "video_status": product.get("video_status") or old.get("video_status", "not_reviewed"),
            "verified": bool(product.get("verified", old.get("verified", False))),
            "approved": bool(product.get("approved", old.get("approved", False))),
            "affiliate_status": product.get("affiliate_status") or old.get("affiliate_status", "unverified"),
            "publishing_status": old.get("publishing_status", "draft_not_published"),
            "approval_required": not bool(product.get("approved", old.get("approved", False))),
        })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(queue),
        "notice": "Drafts only. Publishing requires exact brand/variant verification, current listing checks, a verified Daraz affiliate link, direct social trend evidence, and a reviewed true multi-angle 3D CGI video. 2.5D image motion is not publishable.",
        "items": queue,
    }
    QUEUE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = [
        "id", "opportunity", "product", "brand", "daraz_listing_url", "search_query",
        "listing_verification", "exact_variant", "exact_match_confirmed", "current_price",
        "sold_count", "rating", "stock_status", "seller", "seller_listing_consistent", "listing_verified_at",
        "trend_evidence", "facebook_caption", "instagram_caption", "caption", "reel_hook",
        "video_script", "hashtags", "affiliate_url", "affiliate_link_verified",
        "affiliate_link_verified_at", "public_image_url", "public_video_url",
        "video_cover_url", "video_type", "video_reviewed", "video_status", "verified",
        "approved", "affiliate_status", "publishing_status", "approval_required"
    ]
    with QUEUE_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in queue:
            row = dict(item)
            row["hashtags"] = " ".join(row["hashtags"]) if isinstance(row["hashtags"], list) else row["hashtags"]
            row["trend_evidence"] = json.dumps(row["trend_evidence"], ensure_ascii=False)
            writer.writerow(row)
    print(f"Prepared {len(queue)} product-specific drafts. Unverified items remain unpublished.")


if __name__ == "__main__":
    main()
