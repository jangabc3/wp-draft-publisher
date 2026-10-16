import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "wordpress.py"
SPEC = importlib.util.spec_from_file_location("wp_draft_snapshots", MODULE_PATH)
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


class SnapshotClientTests(unittest.TestCase):
    def test_list_snapshots_is_read_only(self):
        response = {
            "post_id": 42,
            "snapshots": [{"snapshot_id": 8, "operation_id": "op-1"}],
        }
        output = io.StringIO()
        with patch.object(wordpress, "rest_api", return_value=response) as request, redirect_stdout(output):
            wordpress.list_snapshots(42)
        request.assert_called_once_with(
            "GET", "wp-draft-publisher/v1/posts/42/snapshots", soft=True
        )
        self.assertEqual(json.loads(output.getvalue())["snapshots"][0]["snapshot_id"], 8)

    def test_restore_uses_permission_checked_bridge_route(self):
        response = {"ok": True, "post_id": 42, "restored_snapshot_id": 8}
        output = io.StringIO()
        with patch.object(wordpress, "rest_api", return_value=response) as request, redirect_stdout(output):
            wordpress.restore_snapshot(8)
        request.assert_called_once_with(
            "POST", "wp-draft-publisher/v1/snapshots/8/restore", data={}, soft=True
        )
        self.assertTrue(json.loads(output.getvalue())["ok"])

    def test_invalid_snapshot_id_stops_before_network(self):
        with patch.object(wordpress, "rest_api") as request, redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                wordpress.restore_snapshot(0)
        request.assert_not_called()


class ActivityClientTests(unittest.TestCase):
    def test_activity_is_read_only_and_bounded(self):
        response = {"activity": [{"post_id": 42, "action": "update_draft"}]}
        output = io.StringIO()
        with patch.object(wordpress, "rest_api", return_value=response) as request, redirect_stdout(output):
            wordpress.list_activity(25)
        request.assert_called_once_with(
            "GET", "wp-draft-publisher/v1/activity", query={"per_page": 25}, soft=True
        )
        self.assertEqual(json.loads(output.getvalue())["activity"][0]["post_id"], 42)

    def test_invalid_activity_limit_stops_before_network(self):
        with patch.object(wordpress, "rest_api") as request, redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                wordpress.list_activity(101)
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
