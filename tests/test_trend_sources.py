import unittest

from trend_sources import extract_ignix_instagram_product_signals


class IgnixInstagramProductSignalTests(unittest.TestCase):
    def test_extracts_direct_reel_with_product_list_and_views(self):
        html = """
        <h2>Rising on Instagram</h2>
        <div>105.2K views 0:46 Products: @brandone shampoo @brandtwo serum #ProductFinds
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
        self.assertIn("Instagram", rows[0]["source"])

    def test_profile_link_is_not_a_post_permalink(self):
        html = """
        <h2>Rising on Instagram</h2>
        <div>100K views Products: @brand shampoo #beauty
        <a href="https://www.instagram.com/creator/">Creator profile</a></div>
        <h2>What counts as a trend here</h2>
        """
        self.assertEqual(extract_ignix_instagram_product_signals(html), [])

    def test_missing_product_list_is_rejected(self):
        html = """
        <h2>Rising on Instagram</h2>
        <div>100K views Great new routine
        <a href="https://www.instagram.com/reel/ABC123/">Watch</a></div>
        <h2>What counts as a trend here</h2>
        """
        self.assertEqual(extract_ignix_instagram_product_signals(html), [])

    def test_missing_view_metric_is_rejected(self):
        html = """
        <h2>Rising on Instagram</h2>
        <div>Products: @brand shampoo
        <a href="https://www.instagram.com/reel/ABC123/">Watch</a></div>
        <h2>What counts as a trend here</h2>
        """
        self.assertEqual(extract_ignix_instagram_product_signals(html), [])


if __name__ == "__main__":
    unittest.main()
