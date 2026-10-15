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
SPEC = importlib.util.spec_from_file_location("wp_draft_preflight", MODULE_PATH)
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


def valid_payload():
    return {
        "title": "Article title",
        "slug": "article-title",
        "excerpt": "Summary",
        "content": "<p>Opening</p>{{IMAGE_1}}",
        "category_names": ["Guides"],
        "tag_names": ["How-to"],
        "featured_image": {"media_id": 10, "alt": "Featured image"},
        "inline_images": [
            {"marker": "{{IMAGE_1}}", "media_id": 11, "alt": "Inline image"}
        ],
        "image_policy": {"minimum_total": 2, "minimum_inline": 1},
        "seo": {
            "title": "SEO title",
            "description": "SEO description",
            "focus_keyword": "focus keyword",
        },
    }


class MutationFreeValidationTests(unittest.TestCase):
    def assert_preflight_failure(self, value, error):
        output = io.StringIO()
        with patch.object(wordpress, "api") as api_call, patch.object(
            wordpress, "upload_image"
        ) as upload, patch.object(wordpress, "ensure_term") as ensure, redirect_stdout(
            output
        ), self.assertRaises(SystemExit):
            wordpress.prepare_post(value)
        api_call.assert_not_called()
        upload.assert_not_called()
        ensure.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["error"], error)

    def test_root_must_be_an_object(self):
        self.assert_preflight_failure([], "invalid_payload")

    def test_text_fields_must_have_valid_types_and_content(self):
        cases = []
        value = valid_payload()
        value["title"] = 123
        cases.append((value, "invalid_payload_field"))
        value = valid_payload()
        value["content"] = "   "
        cases.append((value, "invalid_payload_field"))
        value = valid_payload()
        value["slug"] = []
        cases.append((value, "invalid_payload_field"))
        value = valid_payload()
        value["excerpt"] = {}
        cases.append((value, "invalid_payload_field"))
        for value, error in cases:
            with self.subTest(value=value):
                self.assert_preflight_failure(value, error)

    def test_taxonomy_lists_and_names_are_validated(self):
        cases = []
        value = valid_payload()
        value["category_names"] = "Guides"
        cases.append((value, "invalid_payload_field"))
        value = valid_payload()
        value["tag_names"] = [""]
        cases.append((value, "invalid_payload_field"))
        value = valid_payload()
        value["category_names"] = ["Guides", " guides "]
        cases.append((value, "duplicate_term_name"))
        for value, error in cases:
            with self.subTest(value=value):
                self.assert_preflight_failure(value, error)

    def test_seo_object_and_all_fields_are_required(self):
        value = valid_payload()
        value["seo"] = "SEO"
        self.assert_preflight_failure(value, "invalid_payload_field")
        for field in ("title", "description", "focus_keyword"):
            value = valid_payload()
            value["seo"][field] = ""
            with self.subTest(field=field):
                self.assert_preflight_failure(value, "invalid_payload_field")

    def test_media_source_must_be_exactly_one_of_id_or_path(self):
        value = valid_payload()
        value["featured_image"] = {"alt": "Missing source"}
        self.assert_preflight_failure(value, "invalid_media_source")
        value = valid_payload()
        value["featured_image"]["path"] = "C:/also-a-path.png"
        self.assert_preflight_failure(value, "invalid_media_source")

    def test_media_ids_must_be_positive_integers(self):
        for media_id in (0, -1, True, "10"):
            value = valid_payload()
            value["featured_image"]["media_id"] = media_id
            with self.subTest(media_id=media_id):
                self.assert_preflight_failure(value, "invalid_media_id")

    def test_alt_text_is_required_and_optional_metadata_must_be_text(self):
        value = valid_payload()
        value["featured_image"]["alt"] = ""
        self.assert_preflight_failure(value, "invalid_payload_field")
        value = valid_payload()
        value["featured_image"]["caption"] = 123
        self.assert_preflight_failure(value, "invalid_payload_field")

    def test_inline_images_must_be_a_list_of_objects(self):
        value = valid_payload()
        value["inline_images"] = "image"
        self.assert_preflight_failure(value, "invalid_payload_field")
        value = valid_payload()
        value["inline_images"] = ["image"]
        self.assert_preflight_failure(value, "invalid_payload_field")

    def test_markers_must_be_unique_and_appear_exactly_once(self):
        value = valid_payload()
        value["content"] = "<p>No marker</p>"
        self.assert_preflight_failure(value, "image_marker_count_invalid")
        value = valid_payload()
        value["content"] += "{{IMAGE_1}}"
        self.assert_preflight_failure(value, "image_marker_count_invalid")
        value = valid_payload()
        value["inline_images"].append(
            {"marker": "{{IMAGE_1}}", "media_id": 12, "alt": "Duplicate marker"}
        )
        self.assert_preflight_failure(value, "duplicate_image_marker")

    def test_image_policy_requires_real_integers(self):
        for policy in (
            [],
            {"minimum_total": True},
            {"minimum_total": "2"},
            {"minimum_inline": False},
        ):
            value = valid_payload()
            value["image_policy"] = policy
            with self.subTest(policy=policy):
                self.assert_preflight_failure(value, "invalid_image_policy")


class LocalImageValidationTests(unittest.TestCase):
    def write_file(self, name, content):
        temporary = tempfile.NamedTemporaryFile(
            dir=TEST_DIRECTORY, prefix="preflight-", suffix=name, delete=False
        )
        temporary.write(content)
        temporary.close()
        path = Path(temporary.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def assert_media_error(self, path, error):
        value = valid_payload()
        value["featured_image"] = {"path": str(path), "alt": "Local image"}
        output = io.StringIO()
        with patch.object(wordpress, "api") as api_call, patch.object(
            wordpress, "upload_image"
        ) as upload, redirect_stdout(output), self.assertRaises(SystemExit):
            wordpress.prepare_post(value)
        api_call.assert_not_called()
        upload.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["error"], error)

    def test_relative_and_missing_paths_are_rejected(self):
        self.assert_media_error(Path("relative.png"), "image_path_not_absolute")
        missing = TEST_DIRECTORY / "not-present.png"
        self.assert_media_error(missing, "image_not_found")

    def test_empty_and_spoofed_images_are_rejected(self):
        self.assert_media_error(self.write_file(".png", b""), "image_file_empty")
        self.assert_media_error(
            self.write_file(".png", b"this is not a png"),
            "unsupported_or_invalid_image",
        )
        self.assert_media_error(
            self.write_file(".svg", b"<svg><script/></svg>"),
            "unsupported_or_invalid_image",
        )

    def test_supported_image_signatures_are_accepted(self):
        cases = {
            ".jpg": b"\xff\xd8\xff" + b"0" * 29,
            ".png": b"\x89PNG\r\n\x1a\n" + b"0" * 24,
            ".gif": b"GIF89a" + b"0" * 26,
            ".webp": b"RIFF" + b"0" * 4 + b"WEBP" + b"0" * 20,
            ".avif": b"0" * 4 + b"ftyp" + b"avif" + b"0" * 20,
        }
        for suffix, content in cases.items():
            with self.subTest(suffix=suffix):
                path = self.write_file(suffix, content)
                self.assertTrue(wordpress.detect_supported_image_mime(path).startswith("image/"))


class RemoteMediaPreflightTests(unittest.TestCase):
    def test_all_existing_media_are_checked_before_any_upload(self):
        value = valid_payload()
        with patch.object(
            wordpress, "api", side_effect=SystemExit(1)
        ) as api_call, patch.object(wordpress, "upload_image") as upload:
            with self.assertRaises(SystemExit):
                wordpress.prepare_post(value)
        api_call.assert_called_once_with("GET", "media/10", query={"context": "edit"})
        upload.assert_not_called()

    def test_invalid_media_response_stops_before_upload(self):
        value = valid_payload()
        with patch.object(
            wordpress,
            "api",
            return_value={"id": 999, "source_url": "https://example.test/wrong.jpg"},
        ) as api_call, patch.object(wordpress, "upload_image") as upload, redirect_stdout(
            io.StringIO()
        ), self.assertRaises(SystemExit):
            wordpress.prepare_post(value)
        api_call.assert_called_once()
        upload.assert_not_called()

    def test_duplicate_media_id_is_preflighted_only_once(self):
        value = valid_payload()
        value["inline_images"][0]["media_id"] = 10
        value["image_policy"]["minimum_total"] = 1
        media = {"id": 10, "source_url": "https://example.test/10.jpg"}
        with patch.object(wordpress, "api", return_value=media) as api_call, patch.object(
            wordpress, "ensure_term", side_effect=[3, 4]
        ):
            post, uploaded, _ = wordpress.prepare_post(value)
        api_call.assert_called_once_with("GET", "media/10", query={"context": "edit"})
        self.assertEqual(uploaded, [10, 10])
        self.assertEqual(post["featured_media"], 10)


if __name__ == "__main__":
    unittest.main()
