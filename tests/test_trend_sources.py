import unittest

from trend_sources import extract_ignix_instagram_product_signals


class IgnixInstagramProductSignalTests(unittest.TestCase):
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
        self.assertIn("Instagram", rows[0]["source"])

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


if __name__ == "__main__":
    unittest.main()
