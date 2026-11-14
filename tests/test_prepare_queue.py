import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import prepare_queue


class PrepareQueueFreshnessTests(unittest.TestCase):
    def test_old_approval_and_verification_are_not_reused(self):
        listing = "https://www.daraz.pk/products/example-i123456.html"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "daraz_candidates.json"
            queue_json = root / "content_queue.json"
            queue_csv = root / "content_queue.csv"

            source.write_text(json.dumps({
                "items": [{
                    "title": "Example product",
                    "url": listing,
                    "social_copy": {
                        "facebook_caption": "Example. Comment ORDER for the link.",
                        "instagram_caption": "Example. Comment ORDER for the link.",
                        "hashtags": ["#Example"],
                    },
                }]
            }), encoding="utf-8")

            old_time = "2026-11-14T10:00:00+00:00"
            queue_json.write_text(json.dumps({
                "items": [{
                    "daraz_listing_url": listing,
                    "brand": "Old Brand",
                    "exact_variant": "Old variant",
                    "exact_match_confirmed": True,
                    "current_price": "Rs. 100",
                    "sold_count": "100 sold",
                    "rating": "5/5",
                    "stock_status": "In stock",
                    "seller": "Old seller",
                    "seller_listing_consistent": True,
                    "listing_verified_at": old_time,
                    "trend_evidence": {
                        "title": "Old Reel",
                        "source_name": "Instagram public post",
                        "source_url": "https://www.instagram.com/reel/OLD/",
                        "observed_at": old_time,
                        "metric": "100K views",
                    },
                    "affiliate_url": "https://s.daraz.pk/s.old",
                    "affiliate_link_verified": True,
                    "affiliate_link_verified_at": old_time,
                    "public_video_url": "https://res.cloudinary.com/example/video/upload/old.mp4",
                    "video_cover_url": "https://res.cloudinary.com/example/image/upload/old.jpg",
                    "video_type": "true_3d_cgi",
                    "video_reviewed": True,
                    "video_status": "reviewed",
                    "verified": True,
                    "approved": True,
                    "affiliate_status": "verified",
                    "publishing_status": "published",
                }]
            }), encoding="utf-8")

            with patch.object(prepare_queue, "SOURCE", source), \\
                 patch.object(prepare_queue, "QUEUE_JSON", queue_json), \\
                 patch.object(prepare_queue, "QUEUE_CSV", queue_csv):
                prepare_queue.main()

            item = json.loads(queue_json.read_text(encoding="utf-8"))["items"][0]
            self.assertFalse(item["verified"])
            self.assertFalse(item["approved"])
            self.assertTrue(item["approval_required"])
            self.assertEqual(item["brand"], "")
            self.assertEqual(item["exact_variant"], "")
            self.assertFalse(item["exact_match_confirmed"])
            self.assertEqual(item["current_price"], "")
            self.assertEqual(item["sold_count"], "")
            self.assertEqual(item["rating"], "")
            self.assertEqual(item["stock_status"], "")
            self.assertEqual(item["seller"], "")
            self.assertFalse(item["seller_listing_consistent"])
            self.assertEqual(item["listing_verified_at"], "")
            self.assertEqual(item["trend_evidence"], {})
            self.assertEqual(item["affiliate_url"], "")
            self.assertFalse(item["affiliate_link_verified"])
            self.assertEqual(item["affiliate_link_verified_at"], "")
            self.assertEqual(item["public_video_url"], "")
            self.assertEqual(item["video_cover_url"], "")
            self.assertEqual(item["video_type"], "not_generated")
            self.assertFalse(item["video_reviewed"])
            self.assertEqual(item["video_status"], "not_reviewed")
            self.assertEqual(item["affiliate_status"], "unverified")
            self.assertEqual(item["publishing_status"], "published")


if __name__ == "__main__":
    unittest.main()
