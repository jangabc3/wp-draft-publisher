import importlib.util
import io
import json
import zipfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "wordpress-plugin" / "wp-draft-publisher-bridge" / "wp-draft-publisher-bridge.php"
MODULE_PATH = ROOT / "scripts" / "wordpress.py"
SPEC = importlib.util.spec_from_file_location("wp_draft_plugin", MODULE_PATH)
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


class PluginSourceTests(unittest.TestCase):
    def test_distribution_zip_uses_portable_forward_slash_paths(self):
        archive = ROOT / "dist" / "wp-draft-publisher-bridge.zip"
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
        self.assertIn(
            "wp-draft-publisher-bridge/wp-draft-publisher-bridge.php", names
        )
        self.assertTrue(all("\\" not in name for name in names))

    def test_plugin_has_permission_checked_rank_math_fields_and_status_route(self):
        source = PLUGIN.read_text(encoding="utf-8")
        for field in ("rank_math_title", "rank_math_description", "rank_math_focus_keyword"):
            self.assertIn(field, source)
        self.assertIn("current_user_can('edit_post', $post_id)", source)
        self.assertIn("'sanitize_callback' => 'sanitize_text_field'", source)
        self.assertIn("'permission_callback' => 'wpdp_bridge_status_permission'", source)
        self.assertIn("wp-draft-publisher/v1", source)

    def test_plugin_has_atomic_draft_only_guard(self):
        source = PLUGIN.read_text(encoding="utf-8")
        self.assertIn("x-wpdp-draft-only", source)
        self.assertIn("'draft' !== get_post_status($post_id)", source)
        self.assertIn("array('status' => 409)", source)
        self.assertIn("add_filter('rest_pre_insert_post'", source)


class BridgeDiagnosticsTests(unittest.TestCase):
    def test_doctor_reports_optional_bridge_capabilities(self):
        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            return {"id": 2, "name": "Editor", "roles": ["editor"]} if endpoint == "users/me" else []

        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "bridge_status", return_value={
                "version": "1.0.0", "atomic_draft_guard": True,
                "rank_math_meta": ["rank_math_title"],
            }
        ), patch.object(wordpress, "SITE", "https://example.test"), patch.object(
            wordpress, "USER", "editor"
        ), patch.object(wordpress, "PASSWORD", "secret"), redirect_stdout(output):
            wordpress.doctor()
        result = json.loads(output.getvalue())
        self.assertTrue(result["checks"]["bridge"]["ok"])
        self.assertTrue(result["checks"]["bridge"]["atomic_draft_guard"])


if __name__ == "__main__":
    unittest.main()
