import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "wordpress.py"
TEST_DIRECTORY = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("wp_draft_dry_run", MODULE_PATH)
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


class DryRunTests(unittest.TestCase):
    def make_png(self):
        temporary = tempfile.NamedTemporaryFile(
            dir=TEST_DIRECTORY, prefix="dry-run-", suffix=".png", delete=False
        )
        temporary.write(b"\x89PNG\r\n\x1a\n" + b"0" * 24)
        temporary.close()
        path = Path(temporary.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def make_payload(self, inline_path=None):
        inline = (
            {"marker": "{{IMAGE_1}}", "path": str(inline_path), "alt": "Inline alt"}
            if inline_path
            else {"marker": "{{IMAGE_1}}", "media_id": 11, "alt": "Inline alt"}
        )
        return {
            "title": "Dry-run title",
            "slug": "dry-run-title",
            "excerpt": "Summary",
            "content": "<p>Opening</p>{{IMAGE_1}}",
            "category_names": ["Guides", "New category"],
            "tag_names": ["How-to"],
            "featured_image": {"media_id": 10, "alt": "Featured alt"},
            "inline_images": [inline],
            "seo": {
                "title": "SEO title",
                "description": "SEO description",
                "focus_keyword": "focus keyword",
            },
        }

    def payload_file(self, payload):
        temporary = tempfile.NamedTemporaryFile(
            mode="w",
            dir=TEST_DIRECTORY,
            prefix="dry-run-",
            suffix=".json",
            encoding="utf-8",
            delete=False,
        )
        json.dump(payload, temporary, ensure_ascii=False)
        temporary.close()
        path = Path(temporary.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_create_dry_run_reports_actions_without_post_requests(self):
        local_image = self.make_png()
        payload_path = self.payload_file(self.make_payload(local_image))
        requests = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            requests.append((method, endpoint, data))
            if endpoint == "posts":
                return []
            if endpoint == "media/10":
                return {"id": 10, "source_url": "https://example.test/10.jpg"}
            if endpoint == "media":
                return []
            if endpoint == "categories":
                if query["search"] == "Guides":
                    return [{"id": 3, "name": "Guides"}]
                return []
            if endpoint == "tags":
                return [{"id": 4, "name": "How-to"}]
            self.fail(f"Unexpected endpoint: {endpoint}")

        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "upload_image"
        ) as upload, patch.object(wordpress, "ensure_term") as ensure, redirect_stdout(output):
            wordpress.dry_run(payload_path)

        self.assertTrue(requests)
        self.assertTrue(all(method == "GET" for method, _, _ in requests))
        upload.assert_not_called()
        ensure.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["would_mutate"])
        self.assertEqual(result["operation"], "create_draft")
        self.assertIsNone(result["target_post_id"])
        self.assertEqual(result["media_actions"][0]["action"], "reuse")
        self.assertEqual(result["media_actions"][1]["action"], "upload")
        self.assertEqual(result["media_actions"][1]["mime_type"], "image/png")
        self.assertEqual(result["category_actions"][0], {"name": "Guides", "action": "reuse", "id": 3})
        self.assertEqual(result["category_actions"][1], {"name": "New category", "action": "create"})
        self.assertEqual(result["tag_actions"][0], {"name": "How-to", "action": "reuse", "id": 4})

    def test_update_dry_run_checks_draft_and_never_posts(self):
        payload_path = self.payload_file(self.make_payload())
        requests = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            requests.append((method, endpoint, data))
            if endpoint == "posts":
                return []
            if endpoint == "posts/42":
                return {"id": 42, "status": "draft"}
            if endpoint == "media/10":
                return {"id": 10, "source_url": "https://example.test/10.jpg"}
            if endpoint == "media/11":
                return {"id": 11, "source_url": "https://example.test/11.jpg"}
            return []

        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), redirect_stdout(output):
            wordpress.dry_run(payload_path, 42)

        self.assertTrue(all(method == "GET" for method, _, _ in requests))
        result = json.loads(output.getvalue())
        self.assertEqual(result["operation"], "update_draft")
        self.assertEqual(result["target_post_id"], 42)

    def test_non_draft_update_stops_before_loading_payload(self):
        with patch.object(
            wordpress, "api", return_value={"id": 42, "status": "publish"}
        ) as api_call, patch.object(wordpress, "load_payload") as load, redirect_stdout(
            io.StringIO()
        ), self.assertRaises(SystemExit):
            wordpress.dry_run("does-not-matter.json", 42)
        api_call.assert_called_once()
        load.assert_not_called()

    def test_invalid_payload_stops_before_network(self):
        value = self.make_payload()
        value["inline_images"][0]["marker"] = "{{MISSING}}"
        payload_path = self.payload_file(value)
        with patch.object(wordpress, "api") as api_call, redirect_stdout(
            io.StringIO()
        ), self.assertRaises(SystemExit):
            wordpress.dry_run(payload_path)
        api_call.assert_not_called()

    def test_remote_media_failure_occurs_before_taxonomy_queries(self):
        payload_path = self.payload_file(self.make_payload())
        requests = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            requests.append((method, endpoint))
            if endpoint == "posts":
                return []
            return {"id": 999, "source_url": "https://example.test/wrong.jpg"}

        with patch.object(wordpress, "api", side_effect=fake_api), redirect_stdout(
            io.StringIO()
        ), self.assertRaises(SystemExit):
            wordpress.dry_run(payload_path)
        self.assertEqual(requests, [("GET", "posts"), ("GET", "media/10")])


if __name__ == "__main__":
    unittest.main()
