"""Shared Pakistan-local daily product cap and audit log for Meta publishing."""

import json
import os
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    PAKISTAN_TZ = ZoneInfo("Asia/Karachi")
except Exception:
    PAKISTAN_TZ = timezone(timedelta(hours=5))

DEFAULT_LOG_PATH = os.getenv("DAILY_PUBLISH_LOG_PATH", "daily_publish_log.json")
MAX_DAILY_PRODUCTS = 5


def current_local_day(now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(PAKISTAN_TZ).date().isoformat()


def load_daily_log(path=DEFAULT_LOG_PATH):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            log = json.load(handle)
        if not isinstance(log, dict):
            raise ValueError("Daily publishing log must be a JSON object.")
        for day, entry in log.items():
            if not isinstance(entry, dict) or not isinstance(entry.get("items", {}), dict):
                raise ValueError(f"Invalid daily publishing log entry for {day}.")
        return log
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Could not read daily publishing log: {exc}") from exc


def can_publish(log, listing_key, platform, brand, today=None, limit=MAX_DAILY_PRODUCTS):
    """Allow each product on both platforms, but cap the day at five distinct brands/products."""
    key = str(listing_key or "").strip()
    brand_name = str(brand or "").strip()
    platform_name = str(platform or "").strip().casefold()
    if not key or not brand_name:
        return False, "a stable Daraz listing key and named brand are required"
    if platform_name not in {"instagram", "facebook"}:
        return False, "platform is not in the approved Meta scope"

    day = today or current_local_day()
    day_entry = log.get(day, {}) if isinstance(log, dict) else {}
    items = day_entry.get("items", {}) if isinstance(day_entry, dict) else {}
    if not isinstance(items, dict):
        return False, "daily log structure is invalid"

    existing = items.get(key)
    if existing is not None:
        if not isinstance(existing, dict):
            return False, "existing daily log item is invalid"
        stored_brand = str(existing.get("brand") or "").strip().casefold()
        if stored_brand and stored_brand != brand_name.casefold():
            return False, "the same listing key is associated with a different brand"
        if str(existing.get(platform_name, {}).get("status") or "").casefold() == "published":
            return False, f"this product is already published on {platform_name} today"
        return True, "same product may still be published to the other Meta platform"

    if len(items) >= limit:
        return False, f"daily cap of {limit} distinct products has been reached"
    used_brands = {
        str(entry.get("brand") or "").strip().casefold()
        for entry in items.values()
        if isinstance(entry, dict) and str(entry.get("brand") or "").strip()
    }
    if brand_name.casefold() in used_brands:
        return False, "a different product from this brand has already been published today"
    return True, "daily product and brand limits allow publishing"


def record_publish(log, listing_key, platform, item, details, today=None):
    key = str(listing_key or "").strip()
    brand = str((item or {}).get("brand") or "").strip()
    platform_name = str(platform or "").strip().casefold()
    if not key or not brand or platform_name not in {"instagram", "facebook"}:
        raise RuntimeError("Cannot record publishing without a stable listing key, brand and approved platform.")

    day = today or current_local_day()
    day_entry = log.setdefault(day, {"items": {}})
    if not isinstance(day_entry, dict):
        raise RuntimeError(f"Invalid daily log entry for {day}.")
    items = day_entry.setdefault("items", {})
    if not isinstance(items, dict):
        raise RuntimeError(f"Invalid daily log item map for {day}.")
    entry = items.setdefault(key, {"brand": brand})
    stored_brand = str(entry.get("brand") or "").strip().casefold()
    if stored_brand and stored_brand != brand.casefold():
        raise RuntimeError("Daily log brand mismatch for the same Daraz listing URL.")

    entry.update({
        "brand": brand,
        "product": item.get("product") or entry.get("product") or "",
        "daraz_listing_url": item.get("daraz_listing_url") or key,
        "exact_variant": item.get("exact_variant") or "",
        "current_price": item.get("current_price") or "",
        "sold_count": item.get("sold_count") or "",
        "rating": item.get("rating") or "",
        "stock_status": item.get("stock_status") or "",
        "seller": item.get("seller") or "",
        "trend_evidence": item.get("trend_evidence") or {},
        "affiliate_url": item.get("affiliate_url") or "",
        "creative": {
            "video_url": item.get("public_video_url") or "",
            "video_type": item.get("video_type") or "",
            "video_aspect_ratio": item.get("video_aspect_ratio") or "",
            "quality_checks": item.get("video_quality_checks") or {},
        },
    })
    entry.setdefault("comments", [])
    entry.setdefault("dm_outcomes", [])
    entry.setdefault("metrics", {})
    entry[platform_name] = details


def save_daily_log(log, path=DEFAULT_LOG_PATH):
    temporary = str(path) + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(log, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)
