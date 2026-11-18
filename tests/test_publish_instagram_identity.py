import unittest

from publish_instagram import validate_target_username, TARGET_INSTAGRAM_USERNAME


class InstagramPublisherIdentityTests(unittest.TestCase):
    def test_intended_profile_is_accepted(self):
        self.assertEqual(
            validate_target_username("official.trending.finds", "official.trending.finds"),
            "official.trending.finds",
        )

    def test_wrong_configured_profile_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "does not match the intended project profile"):
            validate_target_username("mister.unknown.111")

    def test_wrong_live_meta_profile_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Connected Instagram identity mismatch"):
            validate_target_username("official.trending.finds", "mister.unknown.111")

    def test_missing_live_username_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Connected Instagram identity mismatch"):
            validate_target_username("official.trending.finds", "")

    def test_case_and_at_prefix_are_normalized(self):
        self.assertEqual(
            validate_target_username("@OFFICIAL.TRENDING.FINDS", "Official.Trending.Finds"),
            TARGET_INSTAGRAM_USERNAME,
        )


if __name__ == "__main__":
    unittest.main()
