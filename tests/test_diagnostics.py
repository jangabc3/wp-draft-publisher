import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "wordpress.py"
SPEC = importlib.util.spec_from_file_location("wp_draft_diagnostics", MODULE_PATH)
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


class DiagnosticTests(unittest.TestCase):
    def test_doctor_is_read_only_and_reports_each_capability(self):
        calls = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            calls.append((method, endpoint, soft))
            if endpoint == "users/me":
                return {"id": 2, "name": "Editor", "roles": ["editor"]}
            return []

        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "bridge_status", return_value={"_error": "wordpress_http_404"}
        ), patch.object(
            wordpress, "SITE", "https://example.test"
        ), patch.object(wordpress, "USER", "editor"), patch.object(
            wordpress, "PASSWORD", "secret"
        ), redirect_stdout(output):
            wordpress.doctor()
        self.assertTrue(all(method == "GET" for method, _, _ in calls))
        self.assertEqual(len(calls), 5)
        result = json.loads(output.getvalue())
        self.assertTrue(result["ok"])
        self.assertTrue(result["read_only"])
        self.assertEqual(result["user"]["roles"], ["editor"])
        self.assertNotIn("secret", output.getvalue())

    def test_doctor_reports_a_failed_probe_without_mutation(self):
        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            if endpoint == "media":
                return {"_error": "wordpress_http_403"}
            return {"id": 2} if endpoint == "users/me" else []

        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "bridge_status", return_value={"_error": "wordpress_http_404"}
        ), patch.object(
            wordpress, "SITE", "https://example.test"
        ), patch.object(wordpress, "USER", "editor"), patch.object(
            wordpress, "PASSWORD", "secret"
        ), redirect_stdout(output):
            wordpress.doctor()
        result = json.loads(output.getvalue())
        self.assertFalse(result["ok"])
        self.assertEqual(result["checks"]["media_read"]["error"], "wordpress_http_403")

    def test_doctor_returns_detected_categories_permissions_and_site_details(self):
        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            if endpoint == "users/me":
                return {
                    "id": 2, "name": "Editor", "roles": ["editor"],
                    "capabilities": {"edit_posts": True, "upload_files": True, "manage_categories": True},
                }
            if endpoint == "categories":
                return [{"id": 3, "name": "Finance", "slug": "finance"}]
            if endpoint == "tags":
                return [{"id": 4, "name": "Guide", "slug": "guide"}]
            return []

        bridge = {
            "version": "1.5.0", "site_name": "Example", "language": "ko_KR",
            "wordpress_version": "6.8", "home_url": "https://example.test/",
            "seo_providers": ["rank-math"], "active_seo_provider": "rank-math",
        }
        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "bridge_status", return_value=bridge
        ), patch.object(wordpress, "SITE", "https://example.test"), patch.object(
            wordpress, "USER", "editor"
        ), patch.object(wordpress, "PASSWORD", "secret"), redirect_stdout(output):
            wordpress.doctor()
        result = json.loads(output.getvalue())
        self.assertEqual(result["site_details"]["language"], "ko_KR")
        self.assertEqual(result["categories"][0]["name"], "Finance")
        self.assertEqual(result["tags"][0]["name"], "Guide")
        self.assertTrue(result["user"]["permissions"]["create_drafts"])
        self.assertFalse(result["user"]["permissions"]["publish_posts"])

    def test_inspect_returns_summary_without_content(self):
        post = {
            "id": 42, "status": "draft", "slug": "sample",
            "title": {"raw": "Sample"}, "modified": "2026-10-15T10:00:00",
            "featured_media": 9, "categories": [3], "tags": [4],
            "meta": {"rank_math_title": "SEO", "rank_math_description": "Description"},
            "content": {"raw": "private body"}, "link": "https://example.test/?p=42",
        }
        output = io.StringIO()
        with patch.object(wordpress, "api", return_value=post) as api_call, redirect_stdout(output):
            wordpress.inspect_post(42)
        api_call.assert_called_once()
        self.assertEqual(api_call.call_args.args[0], "GET")
        result = json.loads(output.getvalue())
        self.assertEqual(result["post"]["title"], "Sample")
        self.assertNotIn("content", result["post"])
        self.assertTrue(result["post"]["seo"]["title_saved"])
        self.assertFalse(result["post"]["seo"]["focus_keyword_saved"])


if __name__ == "__main__":
    unittest.main()
