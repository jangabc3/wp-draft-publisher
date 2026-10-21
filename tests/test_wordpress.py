import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "wordpress.py"
SPEC = importlib.util.spec_from_file_location("wp_draft_publisher", MODULE_PATH)
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


def valid_payload():
    return {
        "title": "Test title",
        "slug": "test-title",
        "excerpt": "Test excerpt",
        "content": "<p>Opening</p>",
        "category_names": [],
        "tag_names": [],
        "featured_image": {"media_id": 11, "alt": "Featured"},
        "inline_images": [],
        "seo": {
            "title": "SEO title",
            "description": "SEO description",
            "focus_keyword": "keyword",
        },
    }


class PayloadFileMixin:
    def payload_file(self, payload=None):
        temp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=False
        )
        json.dump(payload or valid_payload(), temp, ensure_ascii=False)
        temp.close()
        self.addCleanup(lambda: Path(temp.name).unlink(missing_ok=True))
        return temp.name


class InvalidJsonResponseTests(unittest.TestCase):
    class Response:
        headers = {"Content-Type": "text/html; charset=UTF-8"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"<html>unexpected proxy page</html>"

        def geturl(self):
            return "https://example.test/wp-json/wp/v2/posts"

    def test_invalid_json_response_is_structured_in_soft_mode(self):
        with patch.object(wordpress, "SITE", "https://example.test"), patch.object(
            wordpress, "USER", "editor"
        ), patch.object(wordpress, "PASSWORD", "secret"), patch.object(
            wordpress, "OPEN_URL", return_value=self.Response()
        ):
            result = wordpress.api("GET", "posts", soft=True)

        self.assertEqual(result["_error"], "wordpress_invalid_json_response")
        self.assertEqual(result["_details"]["content_type"], "text/html; charset=UTF-8")
        self.assertIn("unexpected proxy page", result["_details"]["body_prefix"])

    def test_invalid_json_response_reports_clear_hard_failure(self):
        output = io.StringIO()
        with patch.object(wordpress, "SITE", "https://example.test"), patch.object(
            wordpress, "USER", "editor"
        ), patch.object(wordpress, "PASSWORD", "secret"), patch.object(
            wordpress, "OPEN_URL", return_value=self.Response()
        ), redirect_stdout(output), self.assertRaises(SystemExit):
            wordpress.api("GET", "posts")

        result = json.loads(output.getvalue())
        self.assertEqual(result["error"], "wordpress_invalid_json_response")
        self.assertEqual(result["details"]["response_url"], "https://example.test/wp-json/wp/v2/posts")


class UpdateDraftSafetyTests(PayloadFileMixin, unittest.TestCase):
    def assert_rejected_before_mutation(self, status):
        calls = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            calls.append((method, endpoint, data, query))
            return {"id": 42, "status": status}

        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "prepare_post"
        ) as prepare, redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                wordpress.save_draft(self.payload_file(), 42)

        self.assertEqual(raised.exception.code, 1)
        prepare.assert_not_called()
        self.assertEqual(
            calls,
            [("GET", "posts/42", None, {"context": "edit", "_fields": "id,status,modified_gmt"})],
        )
        error = json.loads(output.getvalue())
        self.assertEqual(error["error"], "post_not_draft")
        self.assertEqual(error["details"], {"id": 42, "status": status})

    def test_published_post_is_rejected_before_any_mutation(self):
        self.assert_rejected_before_mutation("publish")

    def test_private_post_is_rejected_before_any_mutation(self):
        self.assert_rejected_before_mutation("private")

    def test_scheduled_post_is_rejected_before_any_mutation(self):
        self.assert_rejected_before_mutation("future")

    def test_pending_post_is_rejected_before_any_mutation(self):
        self.assert_rejected_before_mutation("pending")

    def test_trashed_post_is_rejected_before_any_mutation(self):
        self.assert_rejected_before_mutation("trash")

    def test_missing_status_is_rejected_as_unknown(self):
        calls = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            calls.append((method, endpoint))
            return {"id": 42}

        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "prepare_post"
        ) as prepare, redirect_stdout(output):
            with self.assertRaises(SystemExit):
                wordpress.save_draft(self.payload_file(), 42)

        prepare.assert_not_called()
        self.assertEqual(calls, [("GET", "posts/42")])
        self.assertEqual(json.loads(output.getvalue())["details"]["status"], "unknown")

    def test_mismatched_post_id_is_rejected(self):
        with patch.object(
            wordpress, "api", return_value={"id": 99, "status": "draft"}
        ), patch.object(wordpress, "prepare_post") as prepare, redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                wordpress.save_draft(self.payload_file(), 42)
        prepare.assert_not_called()

    def test_invalid_post_ids_are_rejected_without_api_call(self):
        for invalid_id in (0, -1, True, "42"):
            with self.subTest(post_id=invalid_id), patch.object(
                wordpress, "api"
            ) as api_call, redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    wordpress.save_draft(self.payload_file(), invalid_id)
                api_call.assert_not_called()

    def test_draft_update_never_sends_status_field(self):
        requests = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            requests.append((method, endpoint, data, headers, query, soft))
            if endpoint == "posts":
                return []
            if method == "GET":
                return {"id": 42, "status": "draft", "modified_gmt": "2026-10-16T01:00:00"}
            if data and "meta" in data:
                return {"meta": data["meta"]}
            return {
                "id": 42,
                "status": "draft",
                "link": "https://example.test/?p=42",
            }

        prepared = (
            {"title": "Updated", "content": "Body", "featured_media": 11},
            [11],
            {"rank_math_title": "SEO"},
        )
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "prepare_post", return_value=prepared
        ) as prepare, patch.object(
            wordpress.uuid, "uuid4", return_value="test-operation"
        ), patch.object(
            wordpress, "verify_saved_post", return_value={"modified": "now", "link": "https://example.test/?p=42"}
        ), patch.object(
            wordpress, "SITE", "https://example.test"
        ), redirect_stdout(io.StringIO()):
            wordpress.save_draft(self.payload_file(), 42)

        prepare.assert_called_once()
        self.assertFalse(prepare.call_args.kwargs["include_status"])
        self.assertEqual(requests[0][0:2], ("GET", "posts/42"))
        self.assertEqual(requests[1][0:2], ("GET", "posts"))
        second_draft_read = next(index for index, item in enumerate(requests[1:], start=1) if item[0:2] == ("GET", "posts/42"))
        update_request = next(item for item in requests[second_draft_read + 1:] if item[0:2] == ("POST", "posts/42") and not (item[2] and "meta" in item[2]))
        self.assertEqual(update_request[0:2], ("POST", "posts/42"))
        self.assertNotIn("status", update_request[2])
        self.assertEqual(
            update_request[3],
            {
                "X-WPDP-Agent": "1",
                "X-WPDP-Operation-ID": "test-operation",
                "X-WPDP-Media-IDs": "11",
                "X-WPDP-Draft-Only": "1",
                "X-WPDP-Expected-Modified-GMT": "2026-10-16T01:00:00",
            },
        )

    def test_status_change_during_preparation_stops_post_update(self):
        requests = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            requests.append((method, endpoint, data))
            if endpoint == "posts":
                return []
            get_count = sum(1 for request in requests if request[0] == "GET")
            if get_count == 1:
                return {"id": 42, "status": "draft"}
            return {"id": 42, "status": "publish"}

        prepared = (
            {"title": "Updated", "content": "Body", "featured_media": 11},
            [11],
            {"rank_math_title": "SEO"},
        )
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "prepare_post", return_value=prepared
        ), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                wordpress.save_draft(self.payload_file(), 42)

        self.assertTrue(all(request[0] == "GET" for request in requests))
        self.assertFalse(any(request[0] == "POST" for request in requests))

    def test_modified_draft_is_rejected_before_post_update(self):
        requests = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            requests.append((method, endpoint, data, headers))
            if endpoint == "posts":
                return []
            reads = [item for item in requests if item[0] == "GET" and item[1] == "posts/42"]
            modified = "2026-10-16T01:00:00" if len(reads) == 1 else "2026-10-16T01:01:00"
            return {"id": 42, "status": "draft", "modified_gmt": modified}

        prepared = (
            {"title": "Updated", "content": "Body", "featured_media": 11},
            [11],
            {"rank_math_title": "SEO"},
        )
        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "prepare_post", return_value=prepared
        ), redirect_stdout(output), self.assertRaises(SystemExit):
            wordpress.save_draft(self.payload_file(), 42)

        self.assertFalse(any(item[0] == "POST" for item in requests))
        self.assertEqual(json.loads(output.getvalue())["error"], "post_changed_since_read")


class CreateDraftTests(PayloadFileMixin, unittest.TestCase):
    def test_new_post_is_explicitly_created_as_draft(self):
        with patch.object(
            wordpress,
            "upload_image",
            return_value=(11, "https://example.test/a.jpg"),
        ), patch.object(wordpress, "ensure_term"), patch.object(
            wordpress, "preflight_existing_media", return_value={}
        ):
            post, uploaded, meta = wordpress.prepare_post(valid_payload())

        self.assertEqual(post["status"], "draft")
        self.assertEqual(post["featured_media"], 11)
        self.assertEqual(uploaded, [11])
        self.assertEqual(meta["rank_math_title"], "SEO title")

    def test_update_payload_can_omit_status(self):
        with patch.object(
            wordpress,
            "upload_image",
            return_value=(11, "https://example.test/a.jpg"),
        ), patch.object(wordpress, "ensure_term"), patch.object(
            wordpress, "preflight_existing_media", return_value={}
        ):
            post, _, _ = wordpress.prepare_post(valid_payload(), include_status=False)
        self.assertNotIn("status", post)


class SavedPostVerificationTests(unittest.TestCase):
    def expected_post(self):
        return {
            "title": "Verified title",
            "slug": "verified-title",
            "content": "<p>Verified body</p>",
            "excerpt": "Verified excerpt",
            "featured_media": 11,
            "categories": [3, 2],
            "tags": [5],
        }

    def saved_post(self):
        return {
            "id": 42,
            "status": "draft",
            "slug": "verified-title",
            "title": {"raw": "Verified title"},
            "content": {"raw": "<p>Verified body</p>"},
            "excerpt": {"raw": "Verified excerpt"},
            "featured_media": 11,
            "categories": [2, 3],
            "tags": [5],
            "modified": "2026-10-16T10:00:00",
            "link": "https://example.test/?p=42",
        }

    def test_saved_post_is_read_back_and_verified(self):
        with patch.object(wordpress, "api", return_value=self.saved_post()) as api_call:
            result = wordpress.verify_saved_post(42, self.expected_post())
        self.assertEqual(result["modified"], "2026-10-16T10:00:00")
        self.assertEqual(api_call.call_args.args[0:2], ("GET", "posts/42"))

    def test_content_mismatch_is_reported_without_echoing_content(self):
        saved = self.saved_post()
        saved["content"] = {"raw": "<p>Stale body</p>"}
        output = io.StringIO()
        with patch.object(wordpress, "api", return_value=saved), redirect_stdout(output):
            with self.assertRaises(SystemExit):
                wordpress.verify_saved_post(42, self.expected_post())
        error = json.loads(output.getvalue())
        self.assertEqual(error["error"], "post_verification_failed")
        self.assertEqual(error["details"]["mismatched_fields"], ["content"])
        self.assertNotIn("Stale body", output.getvalue())


class ExistingApiFailureTests(PayloadFileMixin, unittest.TestCase):
    def test_preflight_api_failure_stops_before_payload_processing(self):
        with patch.object(wordpress, "api", side_effect=SystemExit(1)), patch.object(
            wordpress, "load_payload"
        ) as load:
            with self.assertRaises(SystemExit):
                wordpress.save_draft(self.payload_file(), 42)
        load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
