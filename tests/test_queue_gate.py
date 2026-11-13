import unittest
from datetime import datetime, timezone

from queue_gate import validate_queue_payload


def now():
    return datetime.now(timezone.utc).isoformat()


def valid_item(brand="Brand A"):
    return {
        "approved": True,
        "verified": True,
        "product": "Example product",
        "brand": brand,
        "daraz_listing_url": "https://www.daraz.pk/products/example-i123456.html",
        "exact_variant": "Black / 128 GB",
        "exact_match_confirmed": True,
        "current_price": "Rs. 1,250",
        "sold_count": "120 sold",
        "rating": "4.8/5 from 32 ratings",
        "stock_status": "In stock",
        "seller": "Example Store",
        "seller_listing_consistent": True,
        "listing_verified_at": now(),
        "trend_evidence": {
            "title": "Observed product Reel",
            "source_name": "Instagram public post",
            "source_url": "https://www.instagram.com/reel/ABC123/",
            "observed_at": now(),
            "metric": "128K plays; +22K in 24h",
        },
        "affiliate_url": "https://s.daraz.pk/s.example",
        "affiliate_link_verified": True,
        "affiliate_link_verified_at": now(),
        "public_video_url": "https://res.cloudinary.com/example/video/upload/reel.mp4",
        "video_type": "true_3d_cgi",
        "video_reviewed": True,
        "instagram_caption": "A closer look. Comment ORDER for the link.",
        "facebook_caption": "See the details. Comment ORDER for the link.",
    }


class QueueGateTests(unittest.TestCase):
    def test_empty_queue_is_safe(self):
        ready, errors = validate_queue_payload({"items": []})
        self.assertEqual(ready, 0)
        self.assertEqual(errors, [])

    def test_complete_verified_item_passes(self):
        ready, errors = validate_queue_payload({"items": [valid_item()]})
        self.assertEqual(ready, 1)
        self.assertEqual(errors, [])

    def test_2_5d_motion_is_rejected(self):
        item = valid_item()
        item["video_type"] = "2.5d_image_motion"
        ready, errors = validate_queue_payload({"items": [item]})
        self.assertEqual(ready, 0)
        self.assertTrue(any("true_3d_cgi" in error for error in errors))

    def test_duplicate_brands_are_rejected(self):
        ready, errors = validate_queue_payload({"items": [valid_item(), valid_item()]})
        self.assertEqual(ready, 2)
        self.assertTrue(any("duplicate brand" in error for error in errors))

    def test_more_than_five_publishable_items_are_rejected(self):
        items = [valid_item(f"Brand {i}") for i in range(6)]
        ready, errors = validate_queue_payload({"items": items})
        self.assertEqual(ready, 6)
        self.assertTrue(any("At most five" in error for error in errors))

    def test_approved_without_verification_is_rejected(self):
        item = valid_item()
        item["verified"] = False
        ready, errors = validate_queue_payload({"items": [item]})
        self.assertEqual(ready, 0)
        self.assertTrue(any("approved without verified" in error for error in errors))

    def test_stale_listing_check_is_rejected(self):
        item = valid_item()
        item["listing_verified_at"] = "2026-01-01T00:00:00Z"
        ready, errors = validate_queue_payload({"items": [item]})
        self.assertEqual(ready, 0)
        self.assertTrue(any("last 24 hours" in error for error in errors))

    def test_seller_mismatch_is_rejected(self):
        item = valid_item()
        item["seller_listing_consistent"] = False
        ready, errors = validate_queue_payload({"items": [item]})
        self.assertEqual(ready, 0)
        self.assertTrue(any("seller_listing_consistent" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
