import base64
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "wordpress.py"
TEST_DIRECTORY = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("wp_draft_core", MODULE_PATH)
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


def payload():
    return {
        "title": "제목",
        "content": "<p>앞</p>{{ONE}}<p>뒤</p>",
        "featured_image": {"media_id": 10, "alt": "대표"},
        "inline_images": [
            {"marker": "{{ONE}}", "media_id": 11, "alt": 'A & "B"', "caption": "<설명>"}
        ],
        "category_names": ["Guide"],
        "tag_names": ["How-to"],
        "seo": {"title": "SEO", "description": "설명", "focus_keyword": "키워드"},
    }


class FailureAndPayloadTests(unittest.TestCase):
    def test_fail_emits_one_machine_readable_json_object(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            wordpress.fail("problem", {"field": "title"})
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            json.loads(output.getvalue()),
            {"ok": False, "error": "problem", "details": {"field": "title"}},
        )

    def test_load_payload_accepts_utf8_bom(self):
        with tempfile.TemporaryDirectory(dir=TEST_DIRECTORY) as directory:
            path = Path(directory) / "payload.json"
            path.write_text('\ufeff{"title":"ok"}', encoding="utf-8")
            self.assertEqual(wordpress.load_payload(path), {"title": "ok"})

    def test_load_payload_rejects_invalid_json(self):
        with tempfile.TemporaryDirectory(dir=TEST_DIRECTORY) as directory:
            path = Path(directory) / "payload.json"
            path.write_text("{", encoding="utf-8")
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                wordpress.load_payload(path)


class HtmlTests(unittest.TestCase):
    def test_figure_escapes_url_alt_and_caption(self):
        result = wordpress.figure(
            'https://example.test/a?x=1&y="2"', 'A & "B"', "<caption>"
        )
        self.assertIn("x=1&amp;y=&quot;2&quot;", result)
        self.assertIn('alt="A &amp; &quot;B&quot;"', result)
        self.assertIn("&lt;caption&gt;", result)
        self.assertNotIn("<caption>", result)


class TaxonomyTests(unittest.TestCase):
    def test_existing_term_match_is_case_insensitive(self):
        with patch.object(
            wordpress, "api", return_value=[{"id": 7, "name": "Guides"}]
        ) as api_call:
            self.assertEqual(wordpress.ensure_term("categories", "GUIDES"), 7)
        api_call.assert_called_once()

    def test_missing_term_is_created(self):
        with patch.object(
            wordpress,
            "api",
            side_effect=[[], {"id": 8, "name": "New"}],
        ) as api_call:
            self.assertEqual(wordpress.ensure_term("tags", "New"), 8)
        self.assertEqual(api_call.call_count, 2)
        self.assertEqual(api_call.call_args_list[1].args, ("POST", "tags", {"name": "New"}))


class MediaTests(unittest.TestCase):
    def test_existing_media_is_reused_without_upload(self):
        with patch.object(
            wordpress,
            "api",
            return_value={"id": 11, "source_url": "https://example.test/11.jpg"},
        ) as api_call:
            self.assertEqual(
                wordpress.upload_image({"media_id": "11"}),
                (11, "https://example.test/11.jpg"),
            )
        api_call.assert_called_once_with("GET", "media/11", query={"context": "edit"})

    def test_missing_image_file_is_rejected(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            wordpress.upload_image({"path": "definitely-not-present.jpg"})

    def test_new_image_upload_sets_metadata(self):
        with tempfile.TemporaryDirectory(dir=TEST_DIRECTORY) as directory:
            image = Path(directory) / "photo.jpg"
            image.write_bytes(b"jpeg-bytes")
            with patch.object(
                wordpress,
                "api",
                side_effect=[
                    {"id": 21},
                    {"id": 21, "source_url": "https://example.test/photo.jpg"},
                ],
            ) as api_call:
                result = wordpress.upload_image(
                    {"path": str(image), "alt": "Alt", "caption": "Cap", "title": "Title"}
                )
        self.assertEqual(result, (21, "https://example.test/photo.jpg"))
        first = api_call.call_args_list[0]
        self.assertEqual(first.args[0:2], ("POST", "media"))
        self.assertEqual(first.args[2], b"jpeg-bytes")
        self.assertEqual(first.args[3]["Content-Type"], "image/jpeg")
        second = api_call.call_args_list[1]
        self.assertEqual(
            second.args,
            ("POST", "media/21", {"alt_text": "Alt", "caption": "Cap", "title": "Title"}),
        )


class PreparationTests(unittest.TestCase):
    def assert_payload_error(self, value, expected_error):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            wordpress.prepare_post(value)
        self.assertEqual(json.loads(output.getvalue())["error"], expected_error)

    def test_required_fields_are_enforced(self):
        value = payload()
        value.pop("seo")
        self.assert_payload_error(value, "missing_payload_fields")

    def test_invalid_image_policy_is_rejected(self):
        for policy in (
            {"minimum_total": "x"},
            {"minimum_total": 0},
            {"minimum_inline": -1},
        ):
            with self.subTest(policy=policy):
                value = payload()
                value["image_policy"] = policy
                self.assert_payload_error(value, "invalid_image_policy")

    def test_inline_minimum_is_enforced(self):
        value = payload()
        value["inline_images"] = []
        value["image_policy"] = {"minimum_inline": 1}
        self.assert_payload_error(value, "inline_image_policy_not_satisfied")

    def test_unique_image_minimum_is_enforced(self):
        value = payload()
        value["inline_images"][0]["media_id"] = 10
        value["image_policy"] = {"minimum_total": 2}
        self.assert_payload_error(value, "total_image_policy_not_satisfied")

    def test_inline_marker_is_replaced_once_with_safe_figure(self):
        value = payload()
        value["content"] += "{{ONE}}"
        with patch.object(
            wordpress,
            "upload_image",
            side_effect=[
                (10, "https://example.test/featured.jpg"),
                (11, "https://example.test/inline.jpg"),
            ],
        ), patch.object(wordpress, "ensure_term", side_effect=[3, 4]):
            post, uploaded, meta = wordpress.prepare_post(value)
        self.assertEqual(post["categories"], [3])
        self.assertEqual(post["tags"], [4])
        self.assertEqual(uploaded, [10, 11])
        self.assertEqual(post["content"].count("<figure"), 1)
        self.assertEqual(post["content"].count("{{ONE}}"), 1)
        self.assertIn("A &amp; &quot;B&quot;", post["content"])
        self.assertEqual(meta["rank_math_focus_keyword"], "키워드")


class ApiTests(unittest.TestCase):
    def test_missing_credentials_stop_before_network(self):
        with patch.object(wordpress, "SITE", ""), patch.object(
            wordpress, "USER", ""
        ), patch.object(wordpress, "PASSWORD", ""), patch.object(
            wordpress, "OPEN_URL"
        ) as opener, redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            wordpress.api("GET", "posts")
        opener.assert_not_called()

    def test_json_request_uses_basic_auth_and_utf8(self):
        response = MagicMock()
        response.read.return_value = b'{"id":1}'
        response.__enter__.return_value = response
        with patch.object(wordpress, "SITE", "https://example.test"), patch.object(
            wordpress, "USER", "writer"
        ), patch.object(wordpress, "PASSWORD", "secret"), patch.object(
            wordpress, "OPEN_URL", return_value=response
        ) as opener:
            result = wordpress.api("POST", "posts", {"title": "한글"})
        self.assertEqual(result, {"id": 1})
        request = opener.call_args.args[0]
        expected = base64.b64encode(b"writer:secret").decode()
        self.assertEqual(request.get_header("Authorization"), f"Basic {expected}")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"title": "한글"})
        self.assertEqual(request.method, "POST")


class SiteUrlSecurityTests(unittest.TestCase):
    def assert_invalid(self, value, reason):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            wordpress.validate_site_url(value)
        result = json.loads(output.getvalue())
        self.assertEqual(result["error"], "invalid_site_url")
        self.assertEqual(result["details"], reason)

    def test_standard_https_urls_are_accepted(self):
        cases = {
            "https://example.test": "https://example.test",
            " https://example.test/ ": "https://example.test",
            "https://example.test:443": "https://example.test:443",
            "https://example.test/wordpress/": "https://example.test/wordpress",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(wordpress.validate_site_url(value), expected)

    def test_missing_or_malformed_urls_are_rejected(self):
        for value, reason in (
            ("", "missing_url"),
            (None, "missing_url"),
            ("https://", "missing_host"),
            ("https://example.test:invalid", "malformed_url"),
        ):
            with self.subTest(value=value):
                self.assert_invalid(value, reason)

    def test_non_https_schemes_are_rejected(self):
        for value in (
            "http://example.test",
            "ftp://example.test",
            "//example.test",
        ):
            with self.subTest(value=value):
                self.assert_invalid(value, "https_required")

    def test_embedded_credentials_are_rejected(self):
        for value in (
            "https://writer@example.test",
            "https://writer:secret@example.test",
            "https://writer%3Asecret@example.test",
        ):
            with self.subTest(value=value):
                self.assert_invalid(value, "embedded_credentials_not_allowed")

    def test_query_fragment_and_nonstandard_port_are_rejected(self):
        self.assert_invalid(
            "https://example.test?next=https://evil.test",
            "query_or_fragment_not_allowed",
        )
        self.assert_invalid(
            "https://example.test/#section", "query_or_fragment_not_allowed"
        )
        self.assert_invalid(
            "https://example.test:8443", "nonstandard_port_not_allowed"
        )

    def test_ambiguous_characters_are_rejected(self):
        for value in (
            "https://example.test/path with space",
            "https://example.test\\@evil.test",
            "https://example.test\n.evil.test",
        ):
            with self.subTest(value=value):
                self.assert_invalid(value, "invalid_characters")

    def test_redirect_handler_never_creates_followup_request(self):
        handler = wordpress.NoRedirectHandler()
        self.assertIsNone(
            handler.redirect_request(
                MagicMock(),
                None,
                302,
                "Found",
                {},
                "https://evil.test/steal",
            )
        )

    def test_invalid_site_never_reaches_network(self):
        with patch.object(wordpress, "SITE", "http://example.test"), patch.object(
            wordpress, "USER", "writer"
        ), patch.object(wordpress, "PASSWORD", "secret"), patch.object(
            wordpress, "OPEN_URL"
        ) as opener, redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            wordpress.api("GET", "users/me")
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
