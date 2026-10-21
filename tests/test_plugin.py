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
        archive = ROOT / "dist" / "draft-publisher-rest-bridge.zip"
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
        self.assertIn(
            "draft-publisher-rest-bridge/wp-draft-publisher-bridge.php", names
        )
        self.assertTrue(all("\\" not in name for name in names))

    def test_distribution_zip_matches_plugin_source(self):
        archive = ROOT / "dist" / "draft-publisher-rest-bridge.zip"
        source_root = ROOT / "wordpress-plugin" / "wp-draft-publisher-bridge"
        with zipfile.ZipFile(archive) as package:
            for filename in ("readme.txt", "wp-draft-publisher-bridge.php"):
                packaged = package.read(f"draft-publisher-rest-bridge/{filename}")
                source = (source_root / filename).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                self.assertEqual(packaged, source)

    def test_plugin_has_permission_checked_rank_math_fields_and_status_route(self):
        source = PLUGIN.read_text(encoding="utf-8")
        for field in ("rank_math_title", "rank_math_description", "rank_math_focus_keyword"):
            self.assertIn(field, source)
        self.assertIn("current_user_can('edit_post', $post_id)", source)
        self.assertIn("'sanitize_callback' => 'sanitize_text_field'", source)
        self.assertIn("'permission_callback' => 'wpdp_bridge_status_permission'", source)
        self.assertIn("wp-draft-publisher/v1", source)

    def test_plugin_supports_three_seo_providers_and_wordpress_fallback(self):
        source = PLUGIN.read_text(encoding="utf-8")
        for provider in ("rank-math", "yoast", "aioseo", "wordpress"):
            self.assertIn(provider, source)
        for field in ("_yoast_wpseo_title", "_yoast_wpseo_metadesc", "_yoast_wpseo_focuskw"):
            self.assertIn(field, source)
        self.assertIn("AIOSEO\\\\Plugin\\\\Common\\\\Models\\\\Post", source)
        self.assertIn("/posts/(?P<id>\\d+)/seo", source)
        self.assertIn("wpdp_bridge_write_seo", source)
        self.assertIn("'draft' !== get_post_status($post_id)", source)
        self.assertIn("'seo_providers'", source)
        self.assertIn("'active_seo_provider'", source)

    def test_plugin_has_atomic_draft_only_guard(self):
        source = PLUGIN.read_text(encoding="utf-8")
        self.assertIn("x-wpdp-draft-only", source)
        self.assertIn("x-wpdp-expected-modified-gmt", source)
        self.assertIn("post_modified_gmt", source)
        self.assertIn("wpdp_bridge_rest_modified_gmt", source)
        self.assertIn("mysql_to_rfc3339", source)
        self.assertIn("wpdp_post_changed_since_read", source)
        self.assertIn("wpdp_bridge_capture_snapshot", source)
        self.assertIn("/snapshots/(?P<snapshot_id>", source)
        self.assertIn("wpdp_bridge_restore_snapshot", source)
        self.assertIn("WPDP_SNAPSHOT_LIMIT", source)
        self.assertIn("wpdp_bridge_payload_matches_post", source)
        self.assertIn("before_delete_post", source)
        self.assertIn("'recovered' => $recovered", source)
        self.assertIn("'draft' !== get_post_status($post_id)", source)
        self.assertIn("array('status' => 409)", source)
        self.assertIn("add_filter('rest_pre_insert_post'", source)

    def test_plugin_has_privacy_safe_activity_log(self):
        source = PLUGIN.read_text(encoding="utf-8")
        self.assertIn("WPDP_ACTIVITY_POST_TYPE", source)
        self.assertIn("WPDP_ACTIVITY_LIMIT", source)
        self.assertIn("/activity", source)
        self.assertIn("rest_after_insert_post", source)
        self.assertIn("wpdp_bridge_record_activity", source)
        self.assertIn("add_management_page", source)
        self.assertNotIn("_wpdp_post_content", source)

    def test_plugin_has_connection_activity_and_recovery_admin_screen(self):
        for expected in (
            "admin_menu", "Draft Publisher", "Server readiness", "Application Password",
            "Connect Codex or Claude", "wpdp_bridge_recent_snapshots",
            "admin_post_wpdp_restore_snapshot", "check_admin_referer",
            "wpdp_bridge_restore_permission($request)",
            "No publish endpoint is provided",
        ):
            self.assertIn(expected, PLUGIN.read_text(encoding="utf-8"))

    def test_status_reports_site_metadata_for_connection_wizard(self):
        source = PLUGIN.read_text(encoding="utf-8")
        for field in ("site_name", "language", "wordpress_version", "home_url"):
            self.assertIn("'" + field + "'", source)


class BridgeDiagnosticsTests(unittest.TestCase):
    def test_doctor_reports_optional_bridge_capabilities(self):
        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            return {"id": 2, "name": "Editor", "roles": ["editor"]} if endpoint == "users/me" else []

        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(
            wordpress, "bridge_status", return_value={
                "version": "1.2.0", "atomic_draft_guard": True,
                "optimistic_locking": True,
                "snapshots": True, "snapshot_limit": 20,
                "activity_log": True, "activity_limit": 500,
                "rank_math_meta": ["rank_math_title"],
            }
        ), patch.object(wordpress, "SITE", "https://example.test"), patch.object(
            wordpress, "USER", "editor"
        ), patch.object(wordpress, "PASSWORD", "secret"), redirect_stdout(output):
            wordpress.doctor()
        result = json.loads(output.getvalue())
        self.assertTrue(result["checks"]["bridge"]["ok"])
        self.assertTrue(result["checks"]["bridge"]["atomic_draft_guard"])
        self.assertTrue(result["checks"]["bridge"]["optimistic_locking"])
        self.assertTrue(result["checks"]["bridge"]["snapshots"])
        self.assertEqual(result["checks"]["bridge"]["snapshot_limit"], 20)


if __name__ == "__main__":
    unittest.main()
