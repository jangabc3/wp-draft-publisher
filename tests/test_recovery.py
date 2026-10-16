import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "wordpress.py"
SPEC = importlib.util.spec_from_file_location("wp_draft_recovery", MODULE_PATH)
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


def payload():
    return {
        "title": "Recovery",
        "slug": "recovery",
        "content": "<p>Body</p>",
        "category_names": [], "tag_names": [],
        "featured_image": {"media_id": 11, "alt": "Featured"},
        "inline_images": [],
        "seo": {"title": "SEO", "description": "Description", "focus_keyword": "keyword"},
    }


class RecoveryTests(unittest.TestCase):
    def payload_file(self):
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False)
        json.dump(payload(), handle)
        handle.close()
        path = Path(handle.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_get_retries_transient_connection_failures(self):
        response = MagicMock()
        response.read.return_value = b'{"id":1}'
        response.__enter__.return_value = response
        with patch.object(wordpress, "SITE", "https://example.test"), patch.object(
            wordpress, "USER", "writer"
        ), patch.object(wordpress, "PASSWORD", "secret"), patch.object(
            wordpress, "OPEN_URL", side_effect=[URLError("temporary"), response]
        ) as opener, patch.object(wordpress.time, "sleep") as sleep:
            self.assertEqual(wordpress.api("GET", "users/me"), {"id": 1})
        self.assertEqual(opener.call_count, 2)
        sleep.assert_called_once()

    def test_post_is_never_blindly_retried(self):
        with patch.object(wordpress, "SITE", "https://example.test"), patch.object(
            wordpress, "USER", "writer"
        ), patch.object(wordpress, "PASSWORD", "secret"), patch.object(
            wordpress, "OPEN_URL", side_effect=URLError("uncertain")
        ) as opener:
            result = wordpress.api("POST", "posts", {"title": "x"}, soft=True)
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(result["_error"], "wordpress_connection_failed")

    def test_preparation_failure_rolls_back_only_created_media(self):
        created = [31, 32]
        calls = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            calls.append((method, endpoint))
            if endpoint == "posts":
                return []
            if method == "DELETE":
                return {"deleted": True}
            return {"id": 42, "status": "draft"}

        def fail_prepare(*args, **kwargs):
            kwargs["created_media"].extend(created)
            raise SystemExit(1)

        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "prepare_post", side_effect=fail_prepare
        ), redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            wordpress.save_draft(self.payload_file())
        self.assertEqual([call for call in calls if call[0] == "DELETE"], [("DELETE", "media/32"), ("DELETE", "media/31")])

    def test_uncertain_create_recovers_by_slug_without_deleting_media(self):
        calls = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            calls.append((method, endpoint))
            if endpoint == "posts" and method == "GET":
                count = sum(1 for call in calls if call == ("GET", "posts"))
                return [] if count == 1 else [{"id": 55, "status": "draft", "slug": "recovery"}]
            if endpoint == "posts" and method == "POST":
                return {"_error": "wordpress_connection_failed"}
            if endpoint == "posts/55":
                return {"meta": {}}
            return {}

        prepared = ({"title": "Recovery", "slug": "recovery", "status": "draft"}, [31], {})
        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "prepare_post", return_value=prepared
        ), patch.object(
            wordpress, "verify_saved_post", return_value={"modified": "now", "link": "https://example.test/?p=55"}
        ), patch.object(wordpress, "SITE", "https://example.test"), redirect_stdout(output):
            wordpress.save_draft(self.payload_file())
        self.assertFalse(any(method == "DELETE" for method, _ in calls))
        self.assertEqual(json.loads(output.getvalue())["recovery_status"], "recovered_after_uncertain_response")


if __name__ == "__main__":
    unittest.main()
