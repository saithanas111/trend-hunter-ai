import unittest

from publish_instagram import item_key as instagram_item_key
from publish_facebook import item_key as facebook_item_key


class StablePublishingStatusKeyTests(unittest.TestCase):
    def test_both_publishers_use_listing_url_before_queue_position(self):
        item = {
            "id": "1",
            "daraz_listing_url": "https://www.daraz.pk/products/product-a-i123.html",
            "affiliate_url": "https://www.daraz.pk/shop/affiliate-a",
        }
        expected = "https://www.daraz.pk/products/product-a-i123.html"
        self.assertEqual(instagram_item_key(item, 0), expected)
        self.assertEqual(facebook_item_key(item, 0), expected)

    def test_falls_back_to_affiliate_url_when_listing_url_missing(self):
        item = {"id": "1", "affiliate_url": "https://www.daraz.pk/shop/affiliate-a"}
        self.assertEqual(instagram_item_key(item, 0), item["affiliate_url"])
        self.assertEqual(facebook_item_key(item, 0), item["affiliate_url"])


if __name__ == "__main__":
    unittest.main()
