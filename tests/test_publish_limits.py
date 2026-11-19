import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

from publish_limits import (
    can_publish,
    current_local_day,
    load_daily_log,
    record_publish,
    save_daily_log,
)


class DailyPublishLimitTests(unittest.TestCase):
    def test_five_distinct_brands_are_allowed_then_cap_blocks_sixth(self):
        log = {}
        day = "2026-11-19"
        for index in range(5):
            key = f"https://www.daraz.pk/products/item-{index}-i{index}.html"
            allowed, _ = can_publish(log, key, "instagram", f"Brand {index}", today=day)
            self.assertTrue(allowed)
            record_publish(log, key, "instagram", {
                "brand": f"Brand {index}",
                "product": f"Product {index}",
                "daraz_listing_url": key,
            }, {"status": "published", "media_id": str(index)}, today=day)
        allowed, reason = can_publish(
            log,
            "https://www.daraz.pk/products/item-5-i5.html",
            "instagram",
            "Brand 5",
            today=day,
        )
        self.assertFalse(allowed)
        self.assertIn("daily cap", reason)

    def test_same_brand_different_listing_is_blocked(self):
        log = {}
        day = "2026-11-19"
        key1 = "https://www.daraz.pk/products/item-a-i1.html"
        record_publish(log, key1, "instagram", {
            "brand": "Brand A",
            "product": "Product A",
            "daraz_listing_url": key1,
        }, {"status": "published", "media_id": "1"}, today=day)
        allowed, reason = can_publish(
            log,
            "https://www.daraz.pk/products/item-b-i2.html",
            "facebook",
            "brand a",
            today=day,
        )
        self.assertFalse(allowed)
        self.assertIn("brand", reason)

    def test_same_product_can_publish_to_second_platform_but_not_twice_to_one(self):
        log = {}
        day = "2026-11-19"
        key = "https://www.daraz.pk/products/item-a-i1.html"
        record_publish(log, key, "instagram", {
            "brand": "Brand A",
            "product": "Product A",
            "daraz_listing_url": key,
            "trend_evidence": {"metric": "1.8x creator usual"},
        }, {"status": "published", "media_id": "1"}, today=day)
        allowed, _ = can_publish(log, key, "facebook", "Brand A", today=day)
        self.assertTrue(allowed)
        record_publish(log, key, "facebook", {
            "brand": "Brand A",
            "product": "Product A",
            "daraz_listing_url": key,
        }, {"status": "published", "video_id": "2"}, today=day)
        allowed, reason = can_publish(log, key, "instagram", "Brand A", today=day)
        self.assertFalse(allowed)
        self.assertIn("already published", reason)
        self.assertIn("instagram", log[day]["items"][key])
        self.assertIn("facebook", log[day]["items"][key])

    def test_same_listing_with_different_brand_is_blocked(self):
        log = {}
        day = "2026-11-19"
        key = "https://www.daraz.pk/products/item-a-i1.html"
        record_publish(log, key, "instagram", {
            "brand": "Brand A",
            "product": "Product A",
            "daraz_listing_url": key,
        }, {"status": "published"}, today=day)
        allowed, reason = can_publish(log, key, "facebook", "Brand B", today=day)
        self.assertFalse(allowed)
        self.assertIn("different brand", reason)

    def test_daily_log_round_trips(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "daily_publish_log.json"
            log = {}
            key = "https://www.daraz.pk/products/item-a-i1.html"
            record_publish(log, key, "instagram", {
                "brand": "Brand A",
                "product": "Product A",
                "daraz_listing_url": key,
                "trend_evidence": {"metric": "1.8x creator usual"},
                "video_type": "true_3d_cgi",
                "video_aspect_ratio": "9:16",
                "video_quality_checks": {"no_static_zoom": True},
            }, {"status": "published", "media_id": "1"}, today="2026-11-19")
            save_daily_log(log, str(path))
            loaded = load_daily_log(str(path))
            self.assertEqual(loaded["2026-11-19"]["items"][key]["brand"], "Brand A")
            self.assertEqual(loaded["2026-11-19"]["items"][key]["trend_evidence"]["metric"], "1.8x creator usual")
            self.assertEqual(loaded["2026-11-19"]["items"][key]["creative"]["video_aspect_ratio"], "9:16")
            self.assertEqual(loaded["2026-11-19"]["items"][key]["comments"], [])
            self.assertEqual(loaded["2026-11-19"]["items"][key]["dm_outcomes"], [])

    def test_pakistan_local_day_uses_utc_plus_five(self):
        utc = datetime(2026, 11, 19, 19, 30, tzinfo=timezone.utc)
        self.assertEqual(current_local_day(utc), "2026-11-20")


if __name__ == "__main__":
    unittest.main()
