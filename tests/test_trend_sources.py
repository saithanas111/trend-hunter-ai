import unittest

from trend_sources import (
    IGNIX_PRODUCTS_URL,
    extract_ignix_instagram_product_signals,
    qualifies_instagram_product_signal,
)


class IgnixInstagramProductSignalTests(unittest.TestCase):
    def test_tracker_uses_current_instagram_products_route(self):
        self.assertEqual(IGNIX_PRODUCTS_URL, "https://ignix.social/trends/instagram/products")

    def test_extracts_direct_reel_only_when_above_creator_usual(self):
        html = """
        <h2>Rising on Instagram</h2>
        <div>17.9× usual · 105.2K views 0:46 Products: @brandone shampoo @brandtwo serum #ProductFinds
        <a href="https://www.instagram.com/reel/ABC123/">Watch the Reel</a>
        @creator · 447.7K followers</div>
        <h2>What counts as a trend here</h2>
        """
        rows = extract_ignix_instagram_product_signals(
            html, observed_at="2026-11-16T12:00:00+00:00"
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://www.instagram.com/reel/ABC123")
        self.assertIn("brandone shampoo", rows[0]["title"])
        self.assertEqual(rows[0]["views"], "105.2K")
        self.assertEqual(rows[0]["username"], "creator")
        self.assertIn("17.9x creator usual", rows[0]["trend_metric"])
        self.assertEqual(rows[0]["creator_usual_ratio"], 17.9)
        self.assertTrue(qualifies_instagram_product_signal(rows[0]))
        self.assertIn("Instagram", rows[0]["source"])

    def test_accepts_explicit_product_caption_without_products_label(self):
        html = """
        <h2>Rising on Instagram</h2>
        <div>13.8× usual 7.3M views 0:15
        Comment SHOP and I will send the link. The waterproof silicone mat features raised edges to contain spills.
        #HomeEssentials
        <a href="https://www.instagram.com/reel/UNDER123/">Watch the Reel</a>
        @creator · 16.1K followers</div>
        <h2>What counts as a trend here</h2>
        """
        rows = extract_ignix_instagram_product_signals(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://www.instagram.com/reel/UNDER123")
        self.assertIn("silicone mat", rows[0]["title"].lower())
        self.assertIn("13.8x creator usual", rows[0]["trend_metric"])
        self.assertTrue(qualifies_instagram_product_signal(rows[0]))

    def test_creator_summary_ratio_can_be_matched_to_card(self):
        html = """
        <div>Furthest above usual @creator 8.4× usual</div>
        <h2>Rising on Instagram</h2>
        <div>105.2K views 0:46 Products: @brandone shampoo #ProductFinds
        <a href="https://www.instagram.com/p/ABC123/">Watch the Reel</a>
        @creator · 447.7K followers</div>
        <h2>What counts as a trend here</h2>
        """
        rows = extract_ignix_instagram_product_signals(html)
        self.assertEqual(len(rows), 1)
        self.assertIn("8.4x creator usual", rows[0]["trend_metric"])

    def test_below_usual_creator_post_is_rejected(self):
        html = """
        <div>Furthest above usual @creator 0.2× usual</div>
        <h2>Rising on Instagram</h2>
        <div>105.2K views 0:46 Products: @brandone shampoo #ProductFinds
        <a href="https://www.instagram.com/p/ABC123/">Watch the Reel</a>
        @creator · 447.7K followers</div>
        <h2>What counts as a trend here</h2>
        """
        self.assertEqual(extract_ignix_instagram_product_signals(html), [])

    def test_missing_relative_performance_is_rejected(self):
        html = """
        <h2>Rising on Instagram</h2>
        <div>105.2K views 0:46 Products: @brandone shampoo #ProductFinds
        <a href="https://www.instagram.com/reel/ABC123/">Watch the Reel</a>
        @creator · 447.7K followers</div>
        <h2>What counts as a trend here</h2>
        """
        self.assertEqual(extract_ignix_instagram_product_signals(html), [])

    def test_profile_link_is_not_a_post_permalink(self):
        html = """
        <h2>Rising on Instagram</h2>
        <div>17.9× usual 100K views Products: @brand shampoo #beauty
        <a href="https://www.instagram.com/creator/">Creator profile</a>
        @creator · 1K followers</div>
        <h2>What counts as a trend here</h2>
        """
        self.assertEqual(extract_ignix_instagram_product_signals(html), [])

    def test_missing_product_list_is_rejected(self):
        html = """
        <h2>Rising on Instagram</h2>
        <div>17.9× usual 100K views Great new routine
        <a href="https://www.instagram.com/reel/ABC123/">Watch</a>
        @creator · 1K followers</div>
        <h2>What counts as a trend here</h2>
        """
        self.assertEqual(extract_ignix_instagram_product_signals(html), [])

    def test_missing_view_metric_is_rejected(self):
        html = """
        <h2>Rising on Instagram</h2>
        <div>17.9× usual Products: @brand shampoo
        <a href="https://www.instagram.com/reel/ABC123/">Watch</a>
        @creator · 1K followers</div>
        <h2>What counts as a trend here</h2>
        """
        self.assertEqual(extract_ignix_instagram_product_signals(html), [])


class QualifiedSignalGateTests(unittest.TestCase):
    def test_raw_apify_hashtag_post_is_not_a_trend_without_creator_baseline(self):
        self.assertFalse(qualifies_instagram_product_signal({
            "source": "Instagram public hashtag feed via Apify",
            "url": "https://www.instagram.com/reel/ABC123/",
            "title": "Portable blender product Reel",
            "views": "500K",
        }))

    def test_tracker_signal_below_or_equal_to_usual_is_rejected(self):
        for ratio in (0.2, 1.0):
            self.assertFalse(qualifies_instagram_product_signal({
                "source": "Instagram public product Reel via Ignix tracker",
                "url": "https://www.instagram.com/reel/ABC123/",
                "title": "Product Reel",
                "username": "creator",
                "trend_tracker_url": "https://ignix.social/trends/instagram/products",
                "trend_metric": f"{ratio}x creator usual; 100K views",
                "creator_usual_ratio": ratio,
            }))

    def test_tracker_signal_above_usual_with_direct_product_reel_is_accepted(self):
        self.assertTrue(qualifies_instagram_product_signal({
            "source": "Instagram public product Reel via Ignix tracker",
            "url": "https://www.instagram.com/p/ABC123/",
            "title": "Instagram product Reel featuring: branded shampoo",
            "username": "creator",
            "trend_tracker_url": "https://ignix.social/trends/instagram/products",
            "trend_metric": "1.2x creator usual; 100K views",
            "creator_usual_ratio": 1.2,
        }))

    def test_non_instagram_url_is_rejected(self):
        self.assertFalse(qualifies_instagram_product_signal({
            "source": "Instagram public product Reel via Ignix tracker",
            "url": "https://www.facebook.com/reel/ABC123/",
            "title": "Product Reel",
            "username": "creator",
            "trend_tracker_url": "https://ignix.social/trends/instagram/products",
            "trend_metric": "2x creator usual; 100K views",
            "creator_usual_ratio": 2.0,
        }))


if __name__ == "__main__":
    unittest.main()
