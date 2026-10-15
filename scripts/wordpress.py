#!/usr/bin/env python3
import argparse
import base64
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


SITE = os.environ.get("IK_WP_SITE_URL", "").rstrip("/")
USER = os.environ.get("IK_WP_USERNAME", "")
PASSWORD = os.environ.get("IK_WP_APP_PASSWORD", "")


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPEN_URL = build_opener(NoRedirectHandler()).open


def fail(message, details=None):
    payload = {"ok": False, "error": message}
    if details:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(1)


def validate_site_url(value):
    candidate = value.strip().rstrip("/") if isinstance(value, str) else ""
    if not candidate:
        fail("invalid_site_url", "missing_url")
    if any(character.isspace() for character in candidate) or "\\" in candidate:
        fail("invalid_site_url", "invalid_characters")
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError:
        fail("invalid_site_url", "malformed_url")
    if parsed.scheme.lower() != "https":
        fail("invalid_site_url", "https_required")
    if not parsed.hostname:
        fail("invalid_site_url", "missing_host")
    if parsed.username is not None or parsed.password is not None:
        fail("invalid_site_url", "embedded_credentials_not_allowed")
    if parsed.query or parsed.fragment:
        fail("invalid_site_url", "query_or_fragment_not_allowed")
    if port not in (None, 443):
        fail("invalid_site_url", "nonstandard_port_not_allowed")
    return candidate


def api(method, endpoint, data=None, headers=None, query=None, soft=False):
    if not (SITE and USER and PASSWORD):
        fail("missing_credentials")
    site_url = validate_site_url(SITE)
    url = f"{site_url}/wp-json/wp/v2/{endpoint.lstrip('/')}"
    if query:
        url += "?" + urlencode(query)
    auth = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    request_headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    body = data
    if isinstance(data, (dict, list)):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json; charset=utf-8"
    req = Request(url, data=body, headers=request_headers, method=method)
    try:
        with OPEN_URL(req, timeout=90) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = raw[:500]
        if soft:
            return {"_error": f"wordpress_http_{exc.code}", "_details": detail}
        fail(f"wordpress_http_{exc.code}", detail)
    except (URLError, TimeoutError) as exc:
        if soft:
            return {"_error": "wordpress_connection_failed", "_details": str(exc)}
        fail("wordpress_connection_failed", str(exc))


def ensure_term(kind, name):
    results = api("GET", kind, query={"search": name, "per_page": 100, "context": "edit"})
    for item in results:
        if item.get("name", "").casefold() == name.casefold():
            return item["id"]
    return api("POST", kind, {"name": name})["id"]


def upload_image(item, media_cache=None):
    if item.get("media_id"):
        media_id = int(item["media_id"])
        if media_cache is not None and media_id in media_cache:
            media = media_cache[media_id]
        else:
            media = api("GET", f"media/{media_id}", query={"context": "edit"})
        return media["id"], media.get("source_url", "")
    path = Path(item.get("path", ""))
    if not path.is_file():
        fail("image_not_found", str(path))
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    suffix = path.suffix.lower()
    ascii_stem = "".join(ch for ch in path.stem if ch.isascii() and (ch.isalnum() or ch in "-_"))
    upload_name = f"{ascii_stem or ('upload-' + uuid.uuid4().hex[:12])}{suffix}"
    media = api("POST", "media", path.read_bytes(), {
        "Content-Type": mime,
        "Content-Disposition": f'attachment; filename="{upload_name}"',
    })
    update = {
        "alt_text": item.get("alt", ""),
        "caption": item.get("caption", ""),
        "title": item.get("title") or path.stem,
    }
    media = api("POST", f"media/{media['id']}", update)
    return media["id"], media.get("source_url", "")


def figure(url, alt, caption):
    import html
    cap = f"<figcaption>{html.escape(caption)}</figcaption>" if caption else ""
    return (
        '<figure class="wp-block-image size-large">'
        f'<img src="{html.escape(url, quote=True)}" alt="{html.escape(alt, quote=True)}" />'
        f"{cap}</figure>"
    )


def load_payload(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        fail("invalid_payload", str(exc))


def require_nonempty_string(value, field):
    if not isinstance(value, str) or not value.strip():
        fail("invalid_payload_field", field)


def validate_name_list(payload, field):
    values = payload.get(field, [])
    if not isinstance(values, list):
        fail("invalid_payload_field", field)
    seen = set()
    for index, value in enumerate(values):
        require_nonempty_string(value, f"{field}[{index}]")
        normalized = value.strip().casefold()
        if normalized in seen:
            fail("duplicate_term_name", {"field": field, "name": value})
        seen.add(normalized)


def detect_supported_image_mime(path):
    try:
        with path.open("rb") as image_file:
            header = image_file.read(32)
    except OSError as exc:
        fail("image_not_readable", str(exc))
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg", ".jpe", ".jfif") and header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if suffix == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if suffix == ".gif" and header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if suffix == ".webp" and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if suffix == ".avif" and header[4:8] == b"ftyp" and any(
        brand in header[8:32] for brand in (b"avif", b"avis")
    ):
        return "image/avif"
    fail("unsupported_or_invalid_image", str(path))


def validate_media_item(item, field):
    if not isinstance(item, dict):
        fail("invalid_payload_field", field)
    has_media_id = "media_id" in item and item.get("media_id") is not None
    has_path = "path" in item and bool(item.get("path"))
    if has_media_id == has_path:
        fail("invalid_media_source", field)
    require_nonempty_string(item.get("alt"), f"{field}.alt")
    for optional in ("caption", "title"):
        if optional in item and not isinstance(item[optional], str):
            fail("invalid_payload_field", f"{field}.{optional}")
    if has_media_id:
        media_id = item.get("media_id")
        if isinstance(media_id, bool) or not isinstance(media_id, int) or media_id < 1:
            fail("invalid_media_id", field)
        return f"media:{media_id}"
    path_value = item.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        fail("invalid_payload_field", f"{field}.path")
    path = Path(path_value)
    if not path.is_absolute():
        fail("image_path_not_absolute", str(path))
    if not path.is_file():
        fail("image_not_found", str(path))
    try:
        if path.stat().st_size < 1:
            fail("image_file_empty", str(path))
    except OSError as exc:
        fail("image_not_readable", str(exc))
    detect_supported_image_mime(path)
    return f"path:{str(path.resolve()).casefold()}"


def validate_payload(payload):
    if not isinstance(payload, dict):
        fail("invalid_payload", "root_must_be_object")
    required = ["title", "content", "featured_image", "seo"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        fail("missing_payload_fields", missing)
    require_nonempty_string(payload["title"], "title")
    require_nonempty_string(payload["content"], "content")
    for optional in ("slug", "excerpt"):
        if optional in payload and not isinstance(payload[optional], str):
            fail("invalid_payload_field", optional)
    validate_name_list(payload, "category_names")
    validate_name_list(payload, "tag_names")

    seo = payload["seo"]
    if not isinstance(seo, dict):
        fail("invalid_payload_field", "seo")
    for field in ("title", "description", "focus_keyword"):
        require_nonempty_string(seo.get(field), f"seo.{field}")

    inline = payload.get("inline_images", [])
    if not isinstance(inline, list):
        fail("invalid_payload_field", "inline_images")
    policy = payload.get("image_policy", {})
    if not isinstance(policy, dict):
        fail("invalid_image_policy")
    minimum_total = policy.get("minimum_total", 1)
    minimum_inline = policy.get("minimum_inline", 0)
    if (
        isinstance(minimum_total, bool)
        or not isinstance(minimum_total, int)
        or isinstance(minimum_inline, bool)
        or not isinstance(minimum_inline, int)
    ):
        fail("invalid_image_policy")
    if minimum_total < 1 or minimum_inline < 0:
        fail("invalid_image_policy")
    if len(inline) < minimum_inline:
        fail("inline_image_policy_not_satisfied", {"required": minimum_inline, "supplied": len(inline)})

    identities = [validate_media_item(payload["featured_image"], "featured_image")]
    markers = set()
    content = payload["content"]
    for index, item in enumerate(inline):
        field = f"inline_images[{index}]"
        identity = validate_media_item(item, field)
        identities.append(identity)
        marker = item.get("marker")
        require_nonempty_string(marker, f"{field}.marker")
        if marker in markers:
            fail("duplicate_image_marker", marker)
        markers.add(marker)
        occurrences = content.count(marker)
        if occurrences != 1:
            fail(
                "image_marker_count_invalid",
                {"marker": marker, "expected": 1, "found": occurrences},
            )
    if len(set(identities)) < minimum_total:
        fail("total_image_policy_not_satisfied", {"required": minimum_total, "supplied": len(set(identities))})
    return payload


def preflight_existing_media(items):
    media_cache = {}
    for item in items:
        if not item.get("media_id"):
            continue
        media_id = int(item["media_id"])
        if media_id in media_cache:
            continue
        media = api("GET", f"media/{media_id}", query={"context": "edit"})
        if media.get("id") != media_id or not media.get("source_url"):
            fail("invalid_media_response", media_id)
        media_cache[media_id] = media
    return media_cache


def prepare_post(payload, include_status=True):
    validate_payload(payload)
    inline = payload.get("inline_images", [])
    media_cache = preflight_existing_media([payload["featured_image"], *inline])

    featured_id, _ = upload_image(payload["featured_image"], media_cache)
    content = payload["content"]
    uploaded = [featured_id]
    for item in inline:
        marker = item["marker"]
        media_id, url = upload_image(item, media_cache)
        uploaded.append(media_id)
        content = content.replace(marker, figure(url, item.get("alt", ""), item.get("caption", "")), 1)

    categories = [ensure_term("categories", x) for x in payload.get("category_names", [])]
    tags = [ensure_term("tags", x) for x in payload.get("tag_names", [])]
    seo = payload["seo"]
    meta = {
        "rank_math_title": seo.get("title", ""),
        "rank_math_description": seo.get("description", ""),
        "rank_math_focus_keyword": seo.get("focus_keyword", ""),
    }
    post = {
        "title": payload["title"],
        "content": content,
        "excerpt": payload.get("excerpt", ""),
        "slug": payload.get("slug", ""),
        "featured_media": featured_id,
        "categories": categories,
        "tags": tags,
    }
    if include_status:
        post["status"] = "draft"
    return post, uploaded, meta


def assert_draft_post(post_id):
    if isinstance(post_id, bool) or not isinstance(post_id, int) or post_id < 1:
        fail("invalid_post_id", post_id)
    existing = api(
        "GET",
        f"posts/{post_id}",
        query={"context": "edit", "_fields": "id,status"},
    )
    existing_status = existing.get("status")
    if existing.get("id") != post_id or existing_status != "draft":
        fail(
            "post_not_draft",
            {"id": post_id, "status": existing_status or "unknown"},
        )


def save_draft(payload_path, post_id=None):
    if post_id is not None:
        assert_draft_post(post_id)
    payload = load_payload(payload_path)
    post, uploaded, requested_meta = prepare_post(
        payload,
        include_status=post_id is None,
    )
    if post_id is not None:
        assert_draft_post(post_id)
    endpoint = f"posts/{post_id}" if post_id else "posts"
    result = api("POST", endpoint, post)
    seo_result = api("POST", f"posts/{result.get('id')}", {"meta": requested_meta}, soft=True)
    returned_meta = seo_result.get("meta", {}) if not seo_result.get("_error") else {}
    seo_ok = not seo_result.get("_error") and all(
        returned_meta.get(k) == v for k, v in requested_meta.items() if v
    )
    output = {
        "ok": True,
        "id": result.get("id"),
        "status": result.get("status"),
        "link": result.get("link"),
        "preview_url": f"{validate_site_url(SITE)}/?p={result.get('id')}&preview=true",
        "media_count": len(set(uploaded)),
        "seo_status": "saved" if seo_ok else "rank_math_rest_unavailable",
    }
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    draft = sub.add_parser("draft")
    draft.add_argument("--input", required=True)
    update = sub.add_parser("update-draft")
    update.add_argument("--id", required=True, type=int)
    update.add_argument("--input", required=True)
    args = parser.parse_args()
    if args.command == "verify":
        me = api("GET", "users/me", query={"context": "edit"})
        print(json.dumps({"ok": True, "id": me.get("id"), "name": me.get("name"), "roles": me.get("roles", [])}, ensure_ascii=False, separators=(",", ":")))
    elif args.command == "draft":
        save_draft(args.input)
    else:
        save_draft(args.input, args.id)


if __name__ == "__main__":
    main()
