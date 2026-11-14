"""Fail-closed publishing gate for verified, brand-distinct Instagram Reels."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _https_host(value, allowed_suffixes):
    if not _text(value):
        return False
    try:
        parsed = urlparse(value.strip())
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and any(
            host == suffix or host.endswith("." + suffix)
            for suffix in allowed_suffixes
        )
    except Exception:
        return False


def _recent_iso(value, max_age):
    if not _text(value):
        return False
    try:
        raw = value.strip().replace("Z", "+00:00")
        stamp = datetime.fromisoformat(raw)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)
        return timedelta(0) <= age <= max_age
    except (TypeError, ValueError):
        return False


def validate_queue_payload(payload):
    """Return (ready_count, errors). Unapproved drafts are ignored, not published."""
    items = payload.get("items", []) if isinstance(payload, dict) else []
    errors = []
    ready_brands = []

    if not isinstance(items, list):
        return 0, ["Queue items must be a list."]

    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            errors.append(f"Item {index}: queue entry must be an object.")
            continue

        approved = item.get("approved") is True
        verified = item.get("verified") is True
        if approved and not verified:
            errors.append(f"Item {index}: approved without verified=true.")
            continue
        if not (approved and verified):
            continue

        item_errors = []
        brand = str(item.get("brand") or "").strip()
        if not _text(item.get("product")):
            item_errors.append("product title is missing")
        if not brand or brand.casefold() in {"no brand", "unknown", "n/a", "none"}:
            item_errors.append("brand must be a real, named brand (not No Brand)")
        if not _https_host(item.get("daraz_listing_url"), {"daraz.pk"}):
            item_errors.append("daraz_listing_url must be a Daraz Pakistan HTTPS product URL")
        if not _text(item.get("exact_variant")):
            item_errors.append("exact_variant is missing")
        if item.get("exact_match_confirmed") is not True:
            item_errors.append("exact_match_confirmed must be true")
        if not _text(item.get("current_price")):
            item_errors.append("current_price is missing")
        if not _text(item.get("sold_count")):
            item_errors.append("sold_count must contain the displayed count or an explicit 'not displayed' note")
        if not _text(item.get("rating")):
            item_errors.append("rating must contain the displayed rating or an explicit 'not displayed' note")
        stock = str(item.get("stock_status") or "").strip().casefold()
        if not stock:
            item_errors.append("stock_status is missing")
        elif any(word in stock for word in ("out of stock", "unavailable", "not available", "unknown", "not checked")):
            item_errors.append("stock_status is not verified as available")
        elif not any(word in stock for word in ("in stock", "available", "limited stock", "almost sold out", "ready to ship")):
            item_errors.append("stock_status must explicitly confirm availability")
        if not _text(item.get("seller")):
            item_errors.append("seller is missing")
        if item.get("seller_listing_consistent") is not True:
            item_errors.append("seller_listing_consistent must be true")
        if not _recent_iso(item.get("listing_verified_at"), timedelta(hours=24)):
            item_errors.append("listing_verified_at must be a valid check from the last 24 hours")

        evidence = item.get("trend_evidence")
        if not isinstance(evidence, dict):
            item_errors.append("trend_evidence object is missing")
        else:
            if not _text(evidence.get("title")):
                item_errors.append("trend_evidence.title is missing")
            source_name = str(evidence.get("source_name") or "").casefold()
            if not any(platform in source_name for platform in ("instagram", "facebook")):
                item_errors.append("trend_evidence.source_name must identify Instagram or Facebook")
            if not _https_host(evidence.get("source_url"), {"instagram.com", "facebook.com"}):
                item_errors.append("trend_evidence.source_url must be a direct public Instagram/Facebook post URL")
            if not _recent_iso(evidence.get("observed_at"), timedelta(days=7)):
                item_errors.append("trend_evidence.observed_at must be a valid observation from the last 7 days")
            if not _text(evidence.get("metric")):
                item_errors.append("trend_evidence.metric is missing")

        if not _https_host(item.get("affiliate_url"), {"daraz.pk"}):
            item_errors.append("affiliate_url must be a Daraz HTTPS affiliate URL")
        if item.get("affiliate_link_verified") is not True:
            item_errors.append("affiliate_link_verified must be true")
        if not _recent_iso(item.get("affiliate_link_verified_at"), timedelta(hours=24)):
            item_errors.append("affiliate_link_verified_at must be checked within the last 24 hours")

        if not _https_host(item.get("public_video_url"), {"githubusercontent.com", "cloudinary.com", "cloudfront.net"}):
            item_errors.append("public_video_url must be a public HTTPS video URL")
        if item.get("video_type") != "true_3d_cgi":
            item_errors.append("video_type must be true_3d_cgi; 2.5D image motion is not accepted")
        if item.get("video_reviewed") is not True:
            item_errors.append("video_reviewed must be true")

        for field in ("instagram_caption", "facebook_caption"):
            caption = str(item.get(field) or "")
            if "comment order" not in caption.casefold():
                item_errors.append(f"{field} must include a clear 'Comment ORDER' CTA")

        if item_errors:
            errors.extend(f"Item {index}: {message}." for message in item_errors)
        else:
            ready_brands.append(brand.casefold())

    if len(ready_brands) > 5:
        errors.append("At most five publishable products may be queued per daily run.")
    if len(set(ready_brands)) != len(ready_brands):
        errors.append("Publishable products must use five different brands; duplicate brand found.")

    return len(ready_brands), errors
