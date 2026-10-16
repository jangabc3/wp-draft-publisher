import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("wpdp_mcp", SCRIPTS / "mcp_server.py")
mcp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mcp)


class McpProtocolTests(unittest.TestCase):
    def test_initialize_advertises_tools(self):
        response = mcp.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response["id"], 1)
        self.assertIn("tools", response["result"]["capabilities"])
        self.assertEqual(response["result"]["serverInfo"]["name"], "wp-draft-publisher")

    def test_tool_list_contains_safe_draft_workflow(self):
        response = mcp.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {item["name"] for item in response["result"]["tools"]}
        self.assertEqual(names, mcp.TOOL_NAMES)
        self.assertIn("wpdp_save_draft", names)
        self.assertNotIn("publish", names)

    def test_notifications_do_not_return_a_response(self):
        self.assertIsNone(mcp.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_unknown_method_returns_json_rpc_error(self):
        response = mcp.handle_message({"jsonrpc": "2.0", "id": 3, "method": "unknown"})
        self.assertEqual(response["error"]["code"], -32601)

    def test_invalid_arguments_are_a_tool_error(self):
        response = mcp.handle_message({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "wpdp_update_draft", "arguments": {"post_id": 0}},
        })
        self.assertTrue(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["error"], "invalid_arguments")

    def test_restore_requires_explicit_confirmation_argument(self):
        response = mcp.handle_message({
            "jsonrpc": "2.0", "id": 6, "method": "tools/call",
            "params": {"name": "wpdp_restore_snapshot", "arguments": {"snapshot_id": 8}},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("confirm", response["result"]["content"][0]["text"])

    def test_tool_output_is_returned_as_mcp_text(self):
        with patch.object(mcp.wordpress, "inspect_post") as inspect:
            inspect.side_effect = lambda post_id: print(json.dumps({"ok": True, "id": post_id}))
            response = mcp.handle_message({
                "jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {"name": "wpdp_inspect", "arguments": {"post_id": 42}},
            })
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(json.loads(response["result"]["content"][0]["text"])["id"], 42)

    def test_stdio_server_handles_one_request_per_line(self):
        request = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"}) + "\n"
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "mcp_server.py")],
            input=request, text=True, capture_output=True, check=True, timeout=10,
        )
        response = json.loads(completed.stdout.strip())
        self.assertEqual(response, {"jsonrpc": "2.0", "id": 7, "result": {}})


if __name__ == "__main__":
    unittest.main()
