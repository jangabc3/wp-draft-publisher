#!/usr/bin/env python3
"""Small stdio MCP adapter for the safe WordPress draft workflow."""

import io
import json
import sys
from contextlib import redirect_stdout

import wordpress


SERVER_INFO = {"name": "wp-draft-publisher", "version": "1.0.0"}
PROTOCOL_VERSION = "2024-11-05"


TOOLS = [
    {
        "name": "wpdp_doctor",
        "description": "Check WordPress credentials and draft-publisher capabilities without making changes.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "wpdp_dry_run",
        "description": "Validate a payload and preview the exact draft operation without changing WordPress.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "Absolute path to the JSON payload."},
                "post_id": {"type": "integer", "minimum": 1},
            },
            "required": ["input_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "wpdp_save_draft",
        "description": "Create a verified WordPress draft from a validated JSON payload. Never publishes.",
        "inputSchema": {
            "type": "object",
            "properties": {"input_path": {"type": "string"}},
            "required": ["input_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "wpdp_update_draft",
        "description": "Safely update an existing draft with optimistic locking and a recovery snapshot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "integer", "minimum": 1},
                "input_path": {"type": "string"},
            },
            "required": ["post_id", "input_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "wpdp_inspect",
        "description": "Read a compact post summary without returning its article body.",
        "inputSchema": {
            "type": "object", "properties": {"post_id": {"type": "integer", "minimum": 1}},
            "required": ["post_id"], "additionalProperties": False,
        },
    },
    {
        "name": "wpdp_list_snapshots",
        "description": "List private recovery points for a post.",
        "inputSchema": {
            "type": "object", "properties": {"post_id": {"type": "integer", "minimum": 1}},
            "required": ["post_id"], "additionalProperties": False,
        },
    },
    {
        "name": "wpdp_restore_snapshot",
        "description": "Restore a recovery point to its draft after explicit user approval. Published posts are rejected.",
        "inputSchema": {
            "type": "object", "properties": {
                "snapshot_id": {"type": "integer", "minimum": 1},
                "confirm": {"type": "boolean", "const": True, "description": "Set true only after explicit user approval."},
            },
            "required": ["snapshot_id", "confirm"], "additionalProperties": False,
        },
    },
    {
        "name": "wpdp_activity",
        "description": "Read privacy-safe agent operation metadata. Article bodies and credentials are never returned.",
        "inputSchema": {
            "type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            "additionalProperties": False,
        },
    },
]


TOOL_NAMES = {tool["name"] for tool in TOOLS}
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def require(arguments, name, expected_type):
    value = arguments.get(name)
    if expected_type is int and isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer")
    if not isinstance(value, expected_type) or (expected_type is int and value < 1) or (
        expected_type is str and not value.strip()
    ):
        label = "a positive integer" if expected_type is int else "a non-empty string"
        raise ValueError(f"{name} must be {label}")
    return value


def validate_arguments(name, arguments):
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    schema = TOOL_BY_NAME[name]["inputSchema"]
    properties = schema.get("properties", {})
    missing = [field for field in schema.get("required", []) if field not in arguments]
    if missing:
        raise ValueError("missing required arguments: " + ", ".join(missing))
    unexpected = sorted(set(arguments) - set(properties))
    if unexpected:
        raise ValueError("unexpected arguments: " + ", ".join(unexpected))
    for field, value in arguments.items():
        rule = properties[field]
        expected = rule.get("type")
        if expected == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError(f"{field} must be an integer")
        if expected == "string" and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{field} must be a non-empty string")
        if expected == "boolean" and not isinstance(value, bool):
            raise ValueError(f"{field} must be a boolean")
        if "minimum" in rule and value < rule["minimum"]:
            raise ValueError(f"{field} is below the minimum")
        if "maximum" in rule and value > rule["maximum"]:
            raise ValueError(f"{field} exceeds the maximum")
        if "const" in rule and value != rule["const"]:
            raise ValueError(f"{field} must be {rule['const']}")


def invoke_tool(name, arguments):
    if name not in TOOL_NAMES:
        raise ValueError(f"Unknown tool: {name}")
    validate_arguments(name, arguments)
    output = io.StringIO()
    try:
        with redirect_stdout(output):
            if name == "wpdp_doctor":
                wordpress.doctor()
            elif name == "wpdp_dry_run":
                wordpress.dry_run(require(arguments, "input_path", str), arguments.get("post_id"))
            elif name == "wpdp_save_draft":
                wordpress.save_draft(require(arguments, "input_path", str))
            elif name == "wpdp_update_draft":
                wordpress.save_draft(require(arguments, "input_path", str), require(arguments, "post_id", int))
            elif name == "wpdp_inspect":
                wordpress.inspect_post(require(arguments, "post_id", int))
            elif name == "wpdp_list_snapshots":
                wordpress.list_snapshots(require(arguments, "post_id", int))
            elif name == "wpdp_restore_snapshot":
                wordpress.restore_snapshot(require(arguments, "snapshot_id", int))
            elif name == "wpdp_activity":
                wordpress.list_activity(arguments.get("limit", 50))
    except SystemExit as exc:
        text = output.getvalue().strip() or json.dumps({"ok": False, "error": "tool_failed"})
        return text, True if exc.code else False
    return output.getvalue().strip() or json.dumps({"ok": True}), False


def success(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(message):
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid Request")
    method = message.get("method")
    request_id = message.get("id")
    if method and method.startswith("notifications/"):
        return None
    if method == "initialize":
        return success(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        })
    if method == "ping":
        return success(request_id, {})
    if method == "tools/list":
        return success(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params", {})
        try:
            text, is_error = invoke_tool(params.get("name"), params.get("arguments", {}))
            return success(request_id, {
                "content": [{"type": "text", "text": text}],
                "isError": is_error,
            })
        except (TypeError, ValueError) as exc:
            return success(request_id, {
                "content": [{"type": "text", "text": json.dumps({"ok": False, "error": "invalid_arguments", "details": str(exc)})}],
                "isError": True,
            })
    return error(request_id, -32601, "Method not found")


def main():
    for raw_line in sys.stdin:
        try:
            message = json.loads(raw_line)
            response = handle_message(message)
        except json.JSONDecodeError:
            response = error(None, -32700, "Parse error")
        except Exception:
            response = error(None, -32603, "Internal error")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
