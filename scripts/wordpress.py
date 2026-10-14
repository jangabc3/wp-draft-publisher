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
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SITE = os.environ.get("IK_WP_SITE_URL", "").rstrip("/")
USER = os.environ.get("IK_WP_USERNAME", "")
PASSWORD = os.environ.get("IK_WP_APP_PASSWORD", "")


def fail(message, details=None):
    payload = {"ok": False, "error": message}
    if details:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(1)


def api(method, endpoint, data=None, headers=None, query=None, soft=False):
    if not (SITE and USER and PASSWORD):
        fail("missing_credentials")
    url = f"{SITE}/wp-json/wp/v2/{endpoint.lstrip('/')}"
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
        with urlopen(req, timeout=90) as response:
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


def upload_image(item):
    if item.get("media_id"):
        media = api("GET", f"media/{int(item['media_id'])}", query={"context": "edit"})
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


def prepare_post(payload):
    required = ["title", "content", "featured_image", "seo"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        fail("missing_payload_fields", missing)
    inline = payload.get("inline_images", [])
    policy = payload.get("image_policy", {})
    try:
        minimum_total = int(policy.get("minimum_total", 1))
        minimum_inline = int(policy.get("minimum_inline", 0))
    except (TypeError, ValueError):
        fail("invalid_image_policy")
    if minimum_total < 1 or minimum_inline < 0:
        fail("invalid_image_policy")
    if len(inline) < minimum_inline:
        fail("inline_image_policy_not_satisfied", {"required": minimum_inline, "supplied": len(inline)})
    identities = []
    for item in [payload["featured_image"], *inline]:
        identities.append(str(item.get("media_id") or Path(item.get("path", "")).resolve()).casefold())
    if len(set(identities)) < minimum_total:
        fail("total_image_policy_not_satisfied", {"required": minimum_total, "supplied": len(set(identities))})

    featured_id, _ = upload_image(payload["featured_image"])
    content = payload["content"]
    uploaded = [featured_id]
    for item in inline:
        marker = item.get("marker", "")
        if not marker or marker not in content:
            fail("image_marker_missing_from_content", marker)
        media_id, url = upload_image(item)
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
        "status": "draft",
        "featured_media": featured_id,
        "categories": categories,
        "tags": tags,
    }
    return post, uploaded, meta


def save_draft(payload_path, post_id=None):
    payload = load_payload(payload_path)
    post, uploaded, requested_meta = prepare_post(payload)
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
        "preview_url": f"{SITE}/?p={result.get('id')}&preview=true",
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
