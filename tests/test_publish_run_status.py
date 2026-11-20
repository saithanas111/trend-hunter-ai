import json
import os
import tempfile
import unittest

from publish_run_status import write_run_status


class PublishRunStatusTests(unittest.TestCase):
    def test_skipped_run_is_persisted_and_existing_product_status_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "publish_status.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"https://www.daraz.pk/products/item-i1.html": {"status": "published", "media_id": "123"}}, handle)

            record = write_run_status(
                path,
                "instagram",
                "skipped",
                "AUTO_PUBLISH_ENABLED is not true.",
                extra={"expected_username": "official.trending.finds"},
            )

            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["__run__"]["status"], "skipped")
            self.assertEqual(saved["__run__"]["platform"], "instagram")
            self.assertIn("checked_at", saved["__run__"])
            self.assertEqual(saved["https://www.daraz.pk/products/item-i1.html"]["media_id"], "123")
            self.assertEqual(record["reason"], "AUTO_PUBLISH_ENABLED is not true.")

    def test_blocked_run_records_reason_and_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "facebook_publish_status.json")
            record = write_run_status(path, "facebook", "blocked", "Missing Page token.", published_count=0)
            self.assertEqual(record["status"], "blocked")
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["__run__"]["reason"], "Missing Page token.")
            self.assertEqual(saved["__run__"]["published_count"], 0)

    def test_rejects_non_object_status_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "publish_status.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump([], handle)
            with self.assertRaisesRegex(RuntimeError, "Could not read publishing status file"):
                write_run_status(path, "instagram", "skipped", "disabled")


if __name__ == "__main__":
    unittest.main()
