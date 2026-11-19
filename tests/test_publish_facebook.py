import unittest

from publish_facebook import (
    EXPECTED_PAGE_ID,
    EXPECTED_PAGE_NAME,
    format_caption,
    item_key,
    validate_target_page,
    validate_video_url,
)


class FacebookPublisherSafetyTests(unittest.TestCase):
    def test_accepts_only_the_connected_page(self):
        self.assertEqual(
            validate_target_page(
                EXPECTED_PAGE_ID,
                {"id": EXPECTED_PAGE_ID, "name": "Trending Finds"},
            ),
            EXPECTED_PAGE_ID,
        )

    def test_rejects_a_different_page_id(self):
        with self.assertRaises(RuntimeError):
            validate_target_page("123", {"id": "123", "name": "Trending Finds"})

    def test_rejects_a_different_page_name(self):
        with self.assertRaises(RuntimeError):
            validate_target_page(EXPECTED_PAGE_ID, {"id": EXPECTED_PAGE_ID, "name": "Other Page"})

    def test_page_name_comparison_is_case_insensitive(self):
        self.assertEqual(EXPECTED_PAGE_NAME, "trending finds")
        self.assertEqual(
            validate_target_page(EXPECTED_PAGE_ID, {"id": EXPECTED_PAGE_ID, "name": "TRENDING FINDS"}),
            EXPECTED_PAGE_ID,
        )

    def test_caption_contains_affiliate_link_and_order_cta(self):
        caption = format_caption({
            "facebook_caption": "A product preview. Comment ORDER to request the product link.",
            "affiliate_url": "https://www.daraz.pk/shop/affiliate-example",
        })
        self.assertIn("Comment ORDER", caption)
        self.assertIn("https://www.daraz.pk/shop/affiliate-example", caption)

    def test_stable_status_key_prefers_listing_url(self):
        self.assertEqual(
            item_key({"id": "1", "daraz_listing_url": "https://www.daraz.pk/products/item-i1.html"}),
            "https://www.daraz.pk/products/item-i1.html",
        )

    def test_video_url_must_be_mp4_or_mov(self):
        self.assertEqual(
            validate_video_url("https://cdn.example.com/product.mp4"),
            "https://cdn.example.com/product.mp4",
        )
        with self.assertRaises(RuntimeError):
            validate_video_url("https://cdn.example.com/product.jpg")


if __name__ == "__main__":
    unittest.main()
