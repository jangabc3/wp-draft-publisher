import hashlib
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
SPEC = importlib.util.spec_from_file_location("wp_draft_idempotency", MODULE_PATH)
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


def payload():
    return {
        "title": "Same article",
        "slug": "same-article",
        "content": "<p>Body</p>",
        "category_names": [],
        "tag_names": [],
        "featured_image": {"media_id": 11, "alt": "Featured"},
        "inline_images": [],
        "seo": {"title": "SEO", "description": "Description", "focus_keyword": "keyword"},
    }


class IdempotencyTests(unittest.TestCase):
    def payload_file(self):
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False)
        json.dump(payload(), handle)
        handle.close()
        path = Path(handle.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def image_file(self):
        handle = tempfile.NamedTemporaryFile(dir=TEST_DIRECTORY, suffix=".png", delete=False)
        content = b"\x89PNG\r\n\x1a\n" + b"same-image"
        handle.write(content)
        handle.close()
        path = Path(handle.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path, content

    def test_existing_draft_slug_is_reused_without_mutation(self):
        calls = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            calls.append((method, endpoint))
            return [{"id": 77, "status": "draft", "slug": "same-article", "link": "https://example.test/?p=77"}]

        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "prepare_post"
        ) as prepare, patch.object(wordpress, "SITE", "https://example.test"), redirect_stdout(output):
            wordpress.save_draft(self.payload_file())
        prepare.assert_not_called()
        self.assertEqual(calls, [("GET", "posts")])
        result = json.loads(output.getvalue())
        self.assertEqual(result["action"], "reused_existing_draft")
        self.assertEqual(result["id"], 77)

    def test_published_slug_conflict_is_rejected(self):
        with patch.object(
            wordpress,
            "api",
            return_value=[{"id": 80, "status": "publish", "slug": "same-article"}],
        ), redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
            wordpress.save_draft(self.payload_file())
        self.assertEqual(raised.exception.code, 1)

    def test_update_rejects_slug_owned_by_another_post(self):
        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            if endpoint == "posts/42":
                return {"id": 42, "status": "draft"}
            return [{"id": 80, "status": "draft", "slug": "same-article"}]

        with patch.object(wordpress, "api", side_effect=fake_api), redirect_stdout(
            io.StringIO()
        ), self.assertRaises(SystemExit):
            wordpress.save_draft(self.payload_file(), 42)

    def test_local_media_is_reused_by_sha256(self):
        path, content = self.image_file()
        digest = hashlib.sha256(content).hexdigest()
        calls = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            calls.append((method, endpoint, query))
            return [{"id": 21, "slug": f"wpdp-{digest}", "source_url": "https://example.test/image.png"}]

        item = {"path": str(path), "alt": "Alt"}
        with patch.object(wordpress, "api", side_effect=fake_api):
            cache = wordpress.preflight_existing_media([item])
            result = wordpress.upload_image(item, cache)
        self.assertEqual(result, (21, "https://example.test/image.png"))
        self.assertEqual([call[0] for call in calls], ["GET"])

    def test_new_media_uses_content_hash_filename(self):
        path, content = self.image_file()
        digest = hashlib.sha256(content).hexdigest()
        with patch.object(
            wordpress,
            "api",
            side_effect=[{"id": 22}, {"id": 22, "source_url": "https://example.test/image.png"}],
        ) as api_call:
            wordpress.upload_image({"path": str(path), "alt": "Alt"}, {})
        headers = api_call.call_args_list[0].args[3]
        self.assertIn(f'filename="wpdp-{digest}.png"', headers["Content-Disposition"])


if __name__ == "__main__":
    unittest.main()
