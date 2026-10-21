#!/usr/bin/env python3
import argparse
import base64
import csv
import hashlib
import importlib
import json
import mimetypes
import os
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
quality = importlib.import_module("quality")


SITE = os.environ.get("IK_WP_SITE_URL", "").rstrip("/")
USER = os.environ.get("IK_WP_USERNAME", "")
PASSWORD = os.environ.get("IK_WP_APP_PASSWORD", "")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPEN_URL = build_opener(NoRedirectHandler()).open
GET_RETRY_DELAYS = (0.25, 0.75)
TRANSIENT_HTTP_CODES = {429, 502, 503, 504}


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


def rest_api(method, route, data=None, headers=None, query=None, soft=False):
    if not (SITE and USER and PASSWORD):
        if soft:
            return {"_error": "missing_credentials"}
        fail("missing_credentials")
    site_url = validate_site_url(SITE)
    url = f"{site_url}/wp-json/{route.lstrip('/')}"
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
    attempts = 1 + (len(GET_RETRY_DELAYS) if method == "GET" else 0)
    for attempt in range(attempts):
        try:
            with OPEN_URL(req, timeout=90) as response:
                raw = response.read()
                if not raw:
                    return {}
                try:
                    return json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    details = {
                        "content_type": response.headers.get("Content-Type", ""),
                        "response_url": response.geturl(),
                        "body_prefix": raw[:200].decode("utf-8", errors="replace"),
                    }
                    if soft:
                        return {"_error": "wordpress_invalid_json_response", "_details": details}
                    fail("wordpress_invalid_json_response", details)
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw)
            except json.JSONDecodeError:
                detail = raw[:500]
            if method == "GET" and exc.code in TRANSIENT_HTTP_CODES and attempt < attempts - 1:
                time.sleep(GET_RETRY_DELAYS[attempt])
                continue
            if soft:
                return {"_error": f"wordpress_http_{exc.code}", "_details": detail}
            fail(f"wordpress_http_{exc.code}", detail)
        except (URLError, TimeoutError) as exc:
            if method == "GET" and attempt < attempts - 1:
                time.sleep(GET_RETRY_DELAYS[attempt])
                continue
            if soft:
                return {"_error": "wordpress_connection_failed", "_details": str(exc)}
            fail("wordpress_connection_failed", str(exc))


def api(method, endpoint, data=None, headers=None, query=None, soft=False):
    return rest_api(method, f"wp/v2/{endpoint.lstrip('/')}", data, headers, query, soft)


def bridge_status():
    return rest_api("GET", "wp-draft-publisher/v1/status", soft=True)


def find_term(kind, name):
    results = api("GET", kind, query={"search": name, "per_page": 100, "context": "edit"})
    for item in results:
        if item.get("name", "").casefold() == name.casefold():
            return item
    return None


def ensure_term(kind, name):
    existing = find_term(kind, name)
    if existing:
        return existing["id"]
    return api("POST", kind, {"name": name})["id"]


def upload_image(item, media_cache=None, created_media=None):
    if item.get("media_id"):
        media_id = int(item["media_id"])
        cache_key = f"media:{media_id}"
        if media_cache is not None and cache_key in media_cache:
            media = media_cache[cache_key]
        else:
            media = api("GET", f"media/{media_id}", query={"context": "edit"})
        return media["id"], media.get("source_url", "")
    path = Path(item.get("path", ""))
    if not path.is_file():
        fail("image_not_found", str(path))
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    digest = file_sha256(path)
    cache_key = f"hash:{digest}"
    if media_cache is not None and cache_key in media_cache:
        media = media_cache[cache_key]
        return media["id"], media.get("source_url", "")
    suffix = path.suffix.lower()
    upload_name = f"wpdp-{digest}{suffix}"
    media = api("POST", "media", path.read_bytes(), {
        "Content-Type": mime,
        "Content-Disposition": f'attachment; filename="{upload_name}"',
    })
    if created_media is not None:
        created_media.append(media["id"])
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
        return quality.apply_safe_fixes(json.loads(Path(path).read_text(encoding="utf-8-sig")))
    except (OSError, json.JSONDecodeError) as exc:
        fail("invalid_payload", str(exc))


def require_nonempty_string(value, field):
    if not isinstance(value, str) or not value.strip():
        fail("invalid_payload_field", field)


def file_sha256(path):
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        fail("image_not_readable", str(exc))
    return digest.hexdigest()


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
    require_nonempty_string(payload.get("slug"), "slug")
    if "excerpt" in payload and not isinstance(payload["excerpt"], str):
        fail("invalid_payload_field", "excerpt")
    validate_name_list(payload, "category_names")
    validate_name_list(payload, "tag_names")

    seo = payload["seo"]
    if not isinstance(seo, dict):
        fail("invalid_payload_field", "seo")
    for field in ("title", "description", "focus_keyword"):
        require_nonempty_string(seo.get(field), f"seo.{field}")
    provider = seo.get("provider", "auto")
    if provider not in ("auto", "rank-math", "yoast", "aioseo", "none"):
        fail("invalid_payload_field", "seo.provider")
    try:
        quality.validate_policy(payload)
        quality.validate_sources(payload)
    except ValueError as exc:
        fail("invalid_payload_field", str(exc))

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
        if item.get("media_id"):
            media_id = int(item["media_id"])
            cache_key = f"media:{media_id}"
            if cache_key in media_cache:
                continue
            media = api("GET", f"media/{media_id}", query={"context": "edit"})
            if media.get("id") != media_id or not media.get("source_url"):
                fail("invalid_media_response", media_id)
            media_cache[cache_key] = media
            continue
        path = Path(item["path"])
        digest = file_sha256(path)
        cache_key = f"hash:{digest}"
        if cache_key in media_cache:
            continue
        slug = f"wpdp-{digest}"
        matches = api(
            "GET",
            "media",
            query={"slug": slug, "per_page": 100, "context": "edit", "_fields": "id,slug,source_url"},
        )
        exact = [media for media in matches if media.get("slug") == slug]
        if len(exact) > 1:
            fail("duplicate_media_found", {"sha256": digest, "ids": [media.get("id") for media in exact]})
        if exact:
            media = exact[0]
            if not media.get("id") or not media.get("source_url"):
                fail("invalid_media_response", media)
            media_cache[cache_key] = media
    return media_cache


def media_plan(item, role, media_cache):
    if item.get("media_id"):
        media_id = int(item["media_id"])
        media = media_cache[f"media:{media_id}"]
        return {
            "role": role,
            "action": "reuse",
            "media_id": media_id,
            "source_url": media["source_url"],
            "alt": item["alt"],
        }
    path = Path(item["path"])
    digest = file_sha256(path)
    existing = media_cache.get(f"hash:{digest}")
    if existing:
        return {
            "role": role,
            "action": "reuse",
            "reason": "content_hash",
            "media_id": existing["id"],
            "source_url": existing["source_url"],
            "sha256": digest,
            "alt": item["alt"],
        }
    return {
        "role": role,
        "action": "upload",
        "path": str(path),
        "bytes": path.stat().st_size,
        "mime_type": detect_supported_image_mime(path),
        "sha256": digest,
        "upload_name": f"wpdp-{digest}{path.suffix.lower()}",
        "alt": item["alt"],
    }


def taxonomy_plan(kind, names):
    plan = []
    for name in names:
        existing = find_term(kind, name)
        item = {"name": name, "action": "reuse" if existing else "create"}
        if existing:
            item["id"] = existing["id"]
        plan.append(item)
    return plan


def find_posts_by_slug(slug):
    matches = api(
        "GET",
        "posts",
        query={
            "slug": slug,
            "status": "any",
            "context": "edit",
            "per_page": 100,
            "_fields": "id,status,slug,link,modified,modified_gmt",
        },
    )
    return [item for item in matches if item.get("slug") == slug]


def preflight_post_identity(slug, post_id=None):
    matches = find_posts_by_slug(slug)
    conflicts = [item for item in matches if post_id is None or item.get("id") != post_id]
    if not conflicts:
        return None
    if len(conflicts) > 1:
        fail("duplicate_posts_found", {"slug": slug, "ids": [item.get("id") for item in conflicts]})
    existing = conflicts[0]
    if post_id is not None or existing.get("status") != "draft":
        fail("slug_conflict", {"slug": slug, "id": existing.get("id"), "status": existing.get("status")})
    return existing


def seo_plan(payload, status=None):
    requested = payload["seo"].get("provider", "auto")
    status = status if status is not None else bridge_status()
    available = status.get("seo_providers", []) if isinstance(status, dict) and not status.get("_error") else []
    detected = status.get("active_seo_provider") if isinstance(status, dict) and not status.get("_error") else None
    if (
        isinstance(status, dict)
        and "seo_providers" not in status
        and status.get("rank_math_meta")
    ):
        available = ["rank-math"]
        detected = "rank-math"
    if requested == "none":
        selected = "wordpress"
    elif requested == "auto":
        selected = detected or (available[0] if available else "wordpress")
    else:
        selected = requested
    return {
        "requested_provider": requested,
        "selected_provider": selected,
        "available_providers": available,
        "bridge_available": isinstance(status, dict) and not bool(status.get("_error")),
        "fallback": selected == "wordpress",
    }


def save_seo(post_id, payload, operation_id=""):
    plan = seo_plan(payload)
    seo = payload["seo"]
    if plan["selected_provider"] == "wordpress":
        return {**plan, "ok": True, "status": "wordpress_title_excerpt"}
    result = rest_api(
        "POST",
        f"wp-draft-publisher/v1/posts/{post_id}/seo",
        data={
            "provider": plan["selected_provider"],
            "title": seo["title"],
            "description": seo["description"],
            "focus_keyword": seo["focus_keyword"],
            "operation_id": operation_id,
        },
        soft=True,
    )
    if not result.get("_error") and result.get("ok"):
        return {**plan, **result, "status": "saved"}
    if plan["selected_provider"] == "rank-math":
        requested_meta = {
            "rank_math_title": seo["title"],
            "rank_math_description": seo["description"],
            "rank_math_focus_keyword": seo["focus_keyword"],
        }
        legacy = api("POST", f"posts/{post_id}", {"meta": requested_meta}, soft=True)
        returned = legacy.get("meta", {}) if not legacy.get("_error") else {}
        if all(returned.get(key) == value for key, value in requested_meta.items() if value):
            return {**plan, "ok": True, "provider": "rank-math", "status": "saved_legacy_rest"}
    return {**plan, "ok": False, "status": "seo_bridge_unavailable", "details": result}


def get_saved_seo(post_id, provider="auto"):
    result = rest_api("GET", f"wp-draft-publisher/v1/posts/{post_id}/seo", query={"provider": provider}, soft=True)
    if not result.get("_error"):
        return result
    return {"provider": "unknown", "title_saved": False, "description_saved": False, "focus_keyword_saved": False}


def quality_audit(payload, post_id=None):
    report = quality.local_report(payload, SITE)
    policy = quality.policy(payload)
    warnings = list(report["warnings"])
    broken = []
    if policy["check_internal_links"]:
        for link in report.pop("internal_links", []):
            path = urlsplit(link).path.strip("/")
            if not path:
                continue
            slug = path.split("/")[-1]
            found = api("GET", "posts", query={"slug": slug, "status": "any", "context": "edit", "per_page": 1, "_fields": "id,slug"})
            if not found:
                pages = api("GET", "pages", query={"slug": slug, "status": "any", "context": "edit", "per_page": 1, "_fields": "id,slug"})
                if not pages:
                    broken.append(link)
        if broken:
            warnings.append(quality.issue("broken_internal_links", "존재하지 않는 내부 링크가 있습니다.", urls=broken))
    duplicates = []
    if policy["check_duplicate_titles"]:
        candidates = api("GET", "posts", query={"search": payload["title"], "status": "any", "context": "edit", "per_page": 20, "_fields": "id,title,slug,status"})
        for item in candidates:
            if post_id and item.get("id") == post_id:
                continue
            title_value = item.get("title", {})
            if isinstance(title_value, dict):
                title_value = title_value.get("raw") or title_value.get("rendered", "")
            similarity = quality.title_similarity(payload["title"], title_value)
            if similarity >= 0.82:
                duplicates.append({"id": item.get("id"), "title": title_value, "similarity": round(similarity, 2)})
        if duplicates:
            warnings.append(quality.issue("similar_existing_posts", "제목이 매우 비슷한 기존 글이 있습니다.", posts=duplicates))
    report["warnings"] = warnings
    report["checks"]["broken_internal_links"] = len(broken)
    report["checks"]["similar_existing_posts"] = len(duplicates)
    report["score"] = max(0, 100 - len(report["errors"]) * 15 - len(warnings) * 4)
    report["ok"] = not report["errors"] and not (report["mode"] == "strict" and warnings)
    return quality.add_display_summary(report)


def enforce_quality(report):
    if not report["ok"]:
        fail("quality_check_failed", {"mode": report["mode"], "score": report["score"], "errors": report["errors"], "warnings": report["warnings"]})


def dry_run(payload_path, post_id=None):
    if post_id is not None:
        assert_draft_post(post_id)
    payload = load_payload(payload_path)
    validate_payload(payload)
    require_nonempty_string(payload.get("slug"), "slug")
    existing_draft = preflight_post_identity(payload["slug"], post_id)
    quality_report = quality_audit(payload, post_id or (existing_draft or {}).get("id"))
    enforce_quality(quality_report)
    inline = payload.get("inline_images", [])
    media_cache = preflight_existing_media([payload["featured_image"], *inline])
    media_actions = [media_plan(payload["featured_image"], "featured", media_cache)]
    for index, item in enumerate(inline, start=1):
        action = media_plan(item, f"inline:{index}", media_cache)
        action["marker"] = item["marker"]
        media_actions.append(action)
    categories = taxonomy_plan("categories", payload.get("category_names", []))
    tags = taxonomy_plan("tags", payload.get("tag_names", []))
    seo_status = bridge_status()
    planned_seo = seo_plan(payload, seo_status)
    effective_post_id = post_id or (existing_draft or {}).get("id")
    operation = "update_draft" if effective_post_id else "create_draft"
    upload_count = sum(1 for item in media_actions if item.get("action") == "upload")
    reuse_count = sum(1 for item in media_actions if item.get("action") == "reuse")
    category_names = [item.get("name") for item in categories]
    tag_names = [item.get("name") for item in tags]
    provider = planned_seo.get("selected_provider") or planned_seo.get("provider") or "wordpress-default"
    plan = {
        "site_url": SITE,
        "operation": operation,
        "target_post_id": effective_post_id,
        "title": payload["title"],
        "slug": payload.get("slug", ""),
        "categories": category_names,
        "tags": tag_names,
        "media": {"total": len(media_actions), "upload": upload_count, "reuse": reuse_count},
        "seo": {"provider": provider, "status": planned_seo.get("status", "planned")},
        "quality": {
            "status": "passed" if quality_report.get("ok") else "failed",
            "score": quality_report.get("score"),
            "warning_count": len(quality_report.get("warnings", [])),
        },
        "safeguards": {
            "read_only_preview": True,
            "result_status": "draft",
            "published_posts_protected": True,
        },
        "summary": [
            f"{operation}: {payload['title']}",
            f"Categories: {', '.join(category_names) if category_names else 'none'}",
            f"Images: {len(media_actions)} total ({upload_count} upload, {reuse_count} reuse)",
            f"SEO: {provider}; quality: {quality_report.get('score')}/100",
            "This preview is read-only and the eventual result remains a draft.",
        ],
    }
    output = {
        "ok": True,
        "dry_run": True,
        "would_mutate": False,
        "operation": operation,
        "target_post_id": post_id,
        "post_action": "reuse_existing_draft" if existing_draft else ("update" if post_id else "create"),
        "existing_post_id": existing_draft.get("id") if existing_draft else None,
        "title": payload["title"],
        "slug": payload.get("slug", ""),
        "content_characters": len(payload["content"]),
        "media_actions": media_actions,
        "category_actions": categories,
        "tag_actions": tags,
        "seo": {
            "title": payload["seo"]["title"],
            "description": payload["seo"]["description"],
            "focus_keyword": payload["seo"]["focus_keyword"],
            **planned_seo,
        },
        "quality": quality_report,
        "plan": plan,
    }
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


def prepare_post(payload, include_status=True, created_media=None):
    validate_payload(payload)
    inline = payload.get("inline_images", [])
    media_cache = preflight_existing_media([payload["featured_image"], *inline])

    featured_id, _ = upload_image(payload["featured_image"], media_cache, created_media)
    content = payload["content"]
    uploaded = [featured_id]
    for item in inline:
        marker = item["marker"]
        media_id, url = upload_image(item, media_cache, created_media)
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


def assert_draft_post(post_id, expected_modified_gmt=None):
    if isinstance(post_id, bool) or not isinstance(post_id, int) or post_id < 1:
        fail("invalid_post_id", post_id)
    existing = api(
        "GET",
        f"posts/{post_id}",
        query={"context": "edit", "_fields": "id,status,modified_gmt"},
    )
    existing_status = existing.get("status")
    if existing.get("id") != post_id or existing_status != "draft":
        fail(
            "post_not_draft",
            {"id": post_id, "status": existing_status or "unknown"},
        )
    current_modified_gmt = existing.get("modified_gmt")
    if expected_modified_gmt and current_modified_gmt != expected_modified_gmt:
        fail(
            "post_changed_since_read",
            {
                "id": post_id,
                "expected_modified_gmt": expected_modified_gmt,
                "current_modified_gmt": current_modified_gmt or "unknown",
                "guidance": "Read the latest draft, review the changes, and prepare a new update.",
            },
        )
    return existing


def cleanup_created_media(media_ids):
    failures = []
    for media_id in reversed(list(dict.fromkeys(media_ids))):
        result = api("DELETE", f"media/{media_id}", query={"force": "true"}, soft=True)
        if result.get("_error"):
            failures.append({"id": media_id, "error": result["_error"]})
    return failures


def doctor():
    validate_site_url(SITE)
    if not (USER and PASSWORD):
        fail("missing_credentials")
    probes = {
        "authentication": ("users/me", {"context": "edit", "_fields": "id,name,roles,capabilities"}),
        "posts_read": ("posts", {"context": "edit", "per_page": 1, "_fields": "id,status"}),
        "media_read": ("media", {"context": "edit", "per_page": 1, "_fields": "id"}),
        "categories_read": ("categories", {"context": "edit", "per_page": 100, "_fields": "id,name,slug"}),
        "tags_read": ("tags", {"context": "edit", "per_page": 100, "_fields": "id,name,slug"}),
    }
    checks = {}
    user = {}
    categories = []
    tags = []
    for name, (endpoint, query) in probes.items():
        result = api("GET", endpoint, query=query, soft=True)
        checks[name] = {"ok": not bool(result.get("_error")) if isinstance(result, dict) else True}
        if isinstance(result, dict) and result.get("_error"):
            checks[name]["error"] = result["_error"]
        if name == "authentication" and checks[name]["ok"]:
            capabilities = result.get("capabilities", {}) if isinstance(result.get("capabilities"), dict) else {}
            user = {
                "id": result.get("id"),
                "name": result.get("name"),
                "roles": result.get("roles", []),
                "permissions": {
                    "create_drafts": bool(capabilities.get("edit_posts")),
                    "upload_media": bool(capabilities.get("upload_files")),
                    "manage_categories": bool(capabilities.get("manage_categories")),
                    "publish_posts": bool(capabilities.get("publish_posts")),
                },
            }
        elif name == "categories_read" and checks[name]["ok"] and isinstance(result, list):
            categories = [
                {"id": item.get("id"), "name": item.get("name", ""), "slug": item.get("slug", "")}
                for item in result
            ]
        elif name == "tags_read" and checks[name]["ok"] and isinstance(result, list):
            tags = [
                {"id": item.get("id"), "name": item.get("name", ""), "slug": item.get("slug", "")}
                for item in result
            ]
    bridge = bridge_status()
    bridge_available = not bool(bridge.get("_error"))
    checks["bridge"] = {
        "ok": bridge_available,
        "required": False,
        "error": bridge.get("_error") if not bridge_available else None,
        "details": bridge.get("_details") if not bridge_available else None,
        "version": bridge.get("version") if bridge_available else None,
        "atomic_draft_guard": bool(bridge.get("atomic_draft_guard")) if bridge_available else False,
        "optimistic_locking": bool(bridge.get("optimistic_locking")) if bridge_available else False,
        "snapshots": bool(bridge.get("snapshots")) if bridge_available else False,
        "snapshot_limit": bridge.get("snapshot_limit") if bridge_available else None,
        "activity_log": bool(bridge.get("activity_log")) if bridge_available else False,
        "activity_limit": bridge.get("activity_limit") if bridge_available else None,
        "rank_math_meta": bridge.get("rank_math_meta", []) if bridge_available else [],
        "seo_providers": bridge.get("seo_providers", []) if bridge_available else [],
        "active_seo_provider": bridge.get("active_seo_provider") if bridge_available else None,
        "quality_checks": True,
    }
    site_details = {
        "name": bridge.get("site_name") if bridge_available else None,
        "language": bridge.get("language") if bridge_available else None,
        "wordpress_version": bridge.get("wordpress_version") if bridge_available else None,
        "home_url": bridge.get("home_url") if bridge_available else validate_site_url(SITE),
    }
    output = {
        "ok": all(check["ok"] for name, check in checks.items() if name != "bridge"),
        "read_only": True,
        "site": validate_site_url(SITE),
        "site_details": site_details,
        "user": user,
        "categories": categories,
        "tags": tags,
        "checks": checks,
    }
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


def inspect_post(post_id):
    if isinstance(post_id, bool) or not isinstance(post_id, int) or post_id < 1:
        fail("invalid_post_id", post_id)
    post = api(
        "GET",
        f"posts/{post_id}",
        query={
            "context": "edit",
            "_fields": "id,status,slug,title,modified,modified_gmt,featured_media,categories,tags,meta,link",
        },
    )
    meta = post.get("meta", {}) if isinstance(post.get("meta"), dict) else {}
    seo = get_saved_seo(post_id)
    if seo.get("provider") == "unknown":
        seo = {
            "provider": "rank-math" if any(meta.get(key) for key in ("rank_math_title", "rank_math_description", "rank_math_focus_keyword")) else "wordpress",
            "title_saved": bool(meta.get("rank_math_title")),
            "description_saved": bool(meta.get("rank_math_description")),
            "focus_keyword_saved": bool(meta.get("rank_math_focus_keyword")),
        }
    output = {
        "ok": True,
        "read_only": True,
        "post": {
            "id": post.get("id"),
            "status": post.get("status"),
            "slug": post.get("slug"),
            "title": post.get("title", {}).get("raw") or post.get("title", {}).get("rendered", ""),
            "modified": post.get("modified"),
            "modified_gmt": post.get("modified_gmt"),
            "featured_media": post.get("featured_media"),
            "category_ids": post.get("categories", []),
            "tag_ids": post.get("tags", []),
            "link": post.get("link"),
            "seo": seo,
        },
    }
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


def list_snapshots(post_id):
    if isinstance(post_id, bool) or not isinstance(post_id, int) or post_id < 1:
        fail("invalid_post_id", post_id)
    result = rest_api("GET", f"wp-draft-publisher/v1/posts/{post_id}/snapshots", soft=True)
    if result.get("_error"):
        fail("snapshot_bridge_unavailable", result)
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, separators=(",", ":")))


def restore_snapshot(snapshot_id):
    if isinstance(snapshot_id, bool) or not isinstance(snapshot_id, int) or snapshot_id < 1:
        fail("invalid_snapshot_id", snapshot_id)
    result = rest_api(
        "POST",
        f"wp-draft-publisher/v1/snapshots/{snapshot_id}/restore",
        data={},
        soft=True,
    )
    if result.get("_error"):
        fail("snapshot_restore_failed", result)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


def list_activity(limit=50):
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
        fail("invalid_activity_limit", limit)
    result = rest_api(
        "GET",
        "wp-draft-publisher/v1/activity",
        query={"per_page": limit},
        soft=True,
    )
    if result.get("_error"):
        fail("activity_bridge_unavailable", result)
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, separators=(",", ":")))


def load_search_console_export(path):
    if not path:
        return []
    source = Path(path)
    if not source.is_file() or source.stat().st_size > 10 * 1024 * 1024:
        fail("invalid_search_console_export", str(source))
    try:
        if source.suffix.lower() == ".json":
            raw = json.loads(source.read_text(encoding="utf-8-sig"))
            rows = raw.get("rows", []) if isinstance(raw, dict) else raw
        elif source.suffix.lower() == ".csv":
            with source.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        else:
            fail("invalid_search_console_export", "Only CSV and JSON exports are supported.")
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        fail("invalid_search_console_export", str(exc))
    if not isinstance(rows, list):
        fail("invalid_search_console_export", "rows_must_be_array")
    normalized = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            fail("invalid_search_console_row", index)
        lowered = {str(key).strip().casefold().replace(" ", "_"): value for key, value in row.items()}
        keys = row.get("keys")
        api_query = keys[0] if isinstance(keys, list) and keys else ""
        api_page = keys[1] if isinstance(keys, list) and len(keys) > 1 else ""
        query = str(lowered.get("query") or lowered.get("검색어") or lowered.get("인기_검색어") or lowered.get("상위_검색어") or api_query or "").strip()
        page = str(lowered.get("page") or lowered.get("페이지") or lowered.get("인기_페이지") or lowered.get("상위_페이지") or api_page or "").strip()
        if not query:
            continue
        try:
            def number(value):
                return float(str(value).replace(",", "").strip())

            clicks = number(lowered.get("clicks") or lowered.get("클릭수") or lowered.get("클릭") or 0)
            impressions = number(lowered.get("impressions") or lowered.get("노출수") or lowered.get("노출") or 0)
            position = number(lowered.get("position") or lowered.get("게재순위") or lowered.get("순위") or 100)
            ctr_raw = lowered.get("ctr") or lowered.get("클릭률")
            ctr = number(str(ctr_raw).rstrip("%")) / (100 if ctr_raw and "%" in str(ctr_raw) else 1) if ctr_raw not in (None, "") else (clicks / impressions if impressions else 0)
        except (TypeError, ValueError):
            fail("invalid_search_console_row", index)
        if min(clicks, impressions, position, ctr) < 0:
            fail("invalid_search_console_row", index)
        normalized.append({"query": query, "page": page, "clicks": clicks, "impressions": impressions, "ctr": ctr, "position": position})
    return normalized


def fetch_all_inventory(endpoint, query):
    """Read a complete REST collection without assuming a site has <=100 items."""
    collected = []
    for page in range(1, 101):
        page_query = {**query, "per_page": 100, "page": page}
        batch = api("GET", endpoint, query=page_query, soft=True)
        if isinstance(batch, dict) and batch.get("_error"):
            details = batch.get("_details")
            end_of_collection = (
                page > 1
                and batch.get("_error") == "wordpress_http_400"
                and isinstance(details, dict)
                and details.get("code") == "rest_post_invalid_page_number"
            )
            if end_of_collection:
                break
            fail("content_inventory_unavailable", {"endpoint": endpoint, "page": page, "cause": batch})
        if not isinstance(batch, list):
            fail("invalid_content_inventory", endpoint)
        collected.extend(batch)
        if len(batch) < 100:
            break
    else:
        fail("content_inventory_too_large", {"endpoint": endpoint, "maximum_items": 10000})
    return collected


def aggregate_search_queries(rows):
    """Merge duplicate query rows, as Search Console can export one row per page."""
    grouped = {}
    for row in rows:
        key = row["query"].casefold()
        current = grouped.setdefault(key, {**row, "clicks": 0.0, "impressions": 0.0, "weighted_position": 0.0})
        current["clicks"] += row["clicks"]
        current["impressions"] += row["impressions"]
        current["weighted_position"] += row["position"] * max(row["impressions"], 1)
        if not current.get("page") and row.get("page"):
            current["page"] = row["page"]
    output = []
    for current in grouped.values():
        impressions = current["impressions"]
        output.append({
            "query": current["query"], "page": current.get("page", ""),
            "clicks": current["clicks"], "impressions": impressions,
            "ctr": current["clicks"] / impressions if impressions else 0,
            "position": current["weighted_position"] / max(impressions, 1),
        })
    return output


def content_plan(search_console_path=None, weeks=4, per_week=2):
    if isinstance(weeks, bool) or not isinstance(weeks, int) or not 1 <= weeks <= 52:
        fail("invalid_plan_weeks", weeks)
    if isinstance(per_week, bool) or not isinstance(per_week, int) or not 1 <= per_week <= 7:
        fail("invalid_plan_frequency", per_week)
    categories = fetch_all_inventory("categories", {"hide_empty": "false", "context": "edit", "_fields": "id,name,slug,count"})
    posts = fetch_all_inventory("posts", {"status": "any", "context": "edit", "_fields": "id,title,slug,status,link,categories,modified_gmt"})
    compact_posts = []
    for post in posts:
        title_value = post.get("title", {})
        title = (title_value.get("raw") or title_value.get("rendered", "")) if isinstance(title_value, dict) else str(title_value or "")
        compact_posts.append({"id": post.get("id"), "title": title, "slug": post.get("slug"), "status": post.get("status"), "link": post.get("link"), "category_ids": post.get("categories", []), "modified_gmt": post.get("modified_gmt")})
    category_counts = []
    for category in categories:
        actual = sum(1 for post in compact_posts if category.get("id") in post["category_ids"])
        category_counts.append({"id": category.get("id"), "name": category.get("name"), "slug": category.get("slug"), "post_count": actual})
    category_counts.sort(key=lambda item: (item["post_count"], item["name"] or ""))

    duplicates = []
    for index, left in enumerate(compact_posts):
        for right in compact_posts[index + 1:]:
            similarity = quality.title_similarity(left["title"], right["title"])
            if similarity >= 0.82:
                duplicates.append({"post_ids": [left["id"], right["id"]], "titles": [left["title"], right["title"]], "similarity": round(similarity, 2)})

    performance = load_search_console_export(search_console_path)
    aggregated_performance = aggregate_search_queries(performance)
    candidates = []
    for row in aggregated_performance:
        if row["impressions"] < 10:
            continue
        ranked = sorted(((quality.title_similarity(row["query"], post["title"]), post) for post in compact_posts), key=lambda item: item[0], reverse=True)
        best_similarity, best_post = ranked[0] if ranked else (0, None)
        action = "update_existing" if best_post and best_similarity >= 0.55 else "new_article"
        related = [item[1]["id"] for item in ranked[:3] if item[0] >= 0.2]
        opportunity = row["impressions"] * max(0.05, 1 - min(row["ctr"], 1)) / max(row["position"], 1)
        if 5 <= row["position"] <= 20:
            opportunity *= 1.5
        candidates.append({
            "query": row["query"], "action": action, "priority_score": round(opportunity, 2),
            "metrics": {"clicks": row["clicks"], "impressions": row["impressions"], "ctr": round(row["ctr"], 4), "position": row["position"]},
            "existing_post": {"id": best_post["id"], "title": best_post["title"], "similarity": round(best_similarity, 2)} if action == "update_existing" else None,
            "suggested_category": category_counts[0]["name"] if category_counts else None,
            "internal_link_post_ids": related,
            "reason": "high_impressions_low_ctr" if row["ctr"] < 0.03 else ("ranking_5_to_20" if 5 <= row["position"] <= 20 else "search_demand"),
        })
    candidates.sort(key=lambda item: item["priority_score"], reverse=True)
    limit = weeks * per_week
    selected = candidates[:limit]
    start = date.today()
    start += timedelta(days=(7 - start.weekday()) % 7)
    schedule = []
    for index, topic in enumerate(selected):
        week = index // per_week
        day_offset = round((index % per_week) * 7 / per_week)
        schedule.append({"date": (start + timedelta(days=week * 7 + day_offset)).isoformat(), "query": topic["query"], "action": topic["action"], "publish_status": "proposal_only"})
    output = {
        "ok": True, "read_only": True, "would_publish": False,
        "site": validate_site_url(SITE), "site_profile": os.environ.get("WPDP_ACTIVE_SITE", "default"),
        "period": {"weeks": weeks, "articles_per_week": per_week, "maximum_topics": limit},
        "inventory": {"posts": len(compact_posts), "categories": category_counts, "duplicate_title_groups": duplicates},
        "search_console": {"imported": bool(search_console_path), "rows": len(performance), "unique_queries": len(aggregated_performance), "eligible_queries": len(candidates)},
        "recommendations": selected,
        "schedule": schedule,
        "notes": (["Import a Search Console CSV or JSON export to generate demand-based topic recommendations."] if not search_console_path else []) + (["Add or rebalance articles in the least-covered categories shown first."] if category_counts else []),
    }
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


def normalized_saved_text(value):
    if not isinstance(value, str):
        return ""
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def raw_rest_field(post, field):
    value = post.get(field, {})
    if isinstance(value, dict):
        return value.get("raw") or value.get("rendered") or ""
    return value if isinstance(value, str) else ""


def verify_saved_post(post_id, expected_post):
    saved = api(
        "GET",
        f"posts/{post_id}",
        query={
            "context": "edit",
            "_fields": (
                "id,status,slug,title,content,excerpt,featured_media,"
                "categories,tags,modified,modified_gmt,link"
            ),
        },
    )
    mismatches = []
    if saved.get("id") != post_id:
        mismatches.append("id")
    if saved.get("status") != "draft":
        mismatches.append("status")
    if saved.get("slug") != expected_post.get("slug"):
        mismatches.append("slug")
    for field in ("title", "content", "excerpt"):
        if normalized_saved_text(raw_rest_field(saved, field)) != normalized_saved_text(
            expected_post.get(field, "")
        ):
            mismatches.append(field)
    if saved.get("featured_media") != expected_post.get("featured_media"):
        mismatches.append("featured_media")
    for field in ("categories", "tags"):
        if sorted(saved.get(field, [])) != sorted(expected_post.get(field, [])):
            mismatches.append(field)
    if mismatches:
        fail(
            "post_verification_failed",
            {
                "id": post_id,
                "mismatched_fields": mismatches,
                "guidance": "Close every WordPress editor tab for this post, then run update-draft again.",
            },
        )
    return {
        "modified": saved.get("modified"),
        "modified_gmt": saved.get("modified_gmt"),
        "link": saved.get("link"),
    }


def save_draft(payload_path, post_id=None):
    operation_id = str(uuid.uuid4())
    initial_post = None
    if post_id is not None:
        initial_post = assert_draft_post(post_id)
    payload = load_payload(payload_path)
    validate_payload(payload)
    require_nonempty_string(payload.get("slug"), "slug")
    existing_draft = preflight_post_identity(payload["slug"], post_id)
    action = "updated_draft" if post_id is not None else "created_draft"
    if existing_draft:
        post_id = existing_draft.get("id")
        initial_post = assert_draft_post(post_id)
        action = "updated_existing_draft"
    quality_report = quality_audit(payload, post_id)
    enforce_quality(quality_report)
    created_media = []
    try:
        post, uploaded, requested_meta = prepare_post(
            payload,
            include_status=post_id is None,
            created_media=created_media,
        )
        if post_id is not None:
            assert_draft_post(post_id, initial_post.get("modified_gmt") if initial_post else None)
    except SystemExit:
        cleanup_created_media(created_media)
        raise
    endpoint = f"posts/{post_id}" if post_id else "posts"
    media_ids = ",".join(str(item) for item in sorted(set(uploaded)))
    post_headers = {
        "X-WPDP-Agent": "1",
        "X-WPDP-Operation-ID": operation_id,
        "X-WPDP-Media-IDs": media_ids,
    }
    if post_id is not None:
        post_headers["X-WPDP-Draft-Only"] = "1"
        if initial_post and initial_post.get("modified_gmt"):
            post_headers["X-WPDP-Expected-Modified-GMT"] = initial_post["modified_gmt"]
    result = api("POST", endpoint, post, headers=post_headers, soft=True)
    if result.get("_error"):
        recovered = None
        if post_id is None:
            try:
                matches = find_posts_by_slug(payload["slug"])
                exact_drafts = [item for item in matches if item.get("status") == "draft"]
                if len(exact_drafts) == 1:
                    recovered = exact_drafts[0]
            except SystemExit:
                recovered = None
        if recovered:
            result = recovered
            recovery_status = "recovered_after_uncertain_response"
        else:
            cleanup_failures = cleanup_created_media(created_media)
            fail("post_save_failed", {"request": result, "cleanup_failures": cleanup_failures})
    else:
        recovery_status = "not_needed"
    seo_result = save_seo(result.get("id"), payload, operation_id)
    verification = verify_saved_post(result.get("id"), post)
    output = {
        "ok": True,
        "action": action,
        "id": result.get("id"),
        "status": result.get("status"),
        "link": verification.get("link") or result.get("link"),
        "preview_url": f"{validate_site_url(SITE)}/?p={result.get('id')}&preview=true",
        "media_count": len(set(uploaded)),
        "seo_status": seo_result.get("status"),
        "seo_provider": seo_result.get("provider") or seo_result.get("selected_provider"),
        "quality_status": "passed" if quality_report.get("ok") else "failed",
        "quality_score": quality_report.get("score"),
        "quality_warning_count": len(quality_report.get("warnings", [])),
        "quality_warning_codes": [item.get("code") for item in quality_report.get("warnings", [])],
        "quality_display": quality_report.get("display", {}),
        "recovery_status": recovery_status,
        "verification_status": "verified",
        "verified_modified": verification.get("modified"),
        "verified_modified_gmt": verification.get("modified_gmt"),
        "snapshot_id": result.get("wpdp_snapshot_id"),
        "operation_id": result.get("wpdp_operation_id") or operation_id,
    }
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    sub.add_parser("doctor")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--id", required=True, type=int)
    snapshots = sub.add_parser("snapshots")
    snapshots.add_argument("--id", required=True, type=int)
    restore = sub.add_parser("restore-snapshot")
    restore.add_argument("--snapshot-id", required=True, type=int)
    activity = sub.add_parser("activity")
    activity.add_argument("--limit", type=int, default=50)
    plan = sub.add_parser("content-plan")
    plan.add_argument("--search-console")
    plan.add_argument("--weeks", type=int, default=4)
    plan.add_argument("--per-week", type=int, default=2)
    draft = sub.add_parser("draft")
    draft.add_argument("--input", required=True)
    update = sub.add_parser("update-draft")
    update.add_argument("--id", required=True, type=int)
    update.add_argument("--input", required=True)
    preview = sub.add_parser("dry-run")
    preview.add_argument("--input", required=True)
    preview.add_argument("--id", type=int)
    preview_plan = sub.add_parser("preview-plan")
    preview_plan.add_argument("--input", required=True)
    preview_plan.add_argument("--id", type=int)
    quality_check = sub.add_parser("quality-check")
    quality_check.add_argument("--input", required=True)
    quality_check.add_argument("--id", type=int)
    args = parser.parse_args()
    if args.command == "verify":
        me = api("GET", "users/me", query={"context": "edit"})
        print(json.dumps({"ok": True, "id": me.get("id"), "name": me.get("name"), "roles": me.get("roles", [])}, ensure_ascii=False, separators=(",", ":")))
    elif args.command == "doctor":
        doctor()
    elif args.command == "inspect":
        inspect_post(args.id)
    elif args.command == "snapshots":
        list_snapshots(args.id)
    elif args.command == "restore-snapshot":
        restore_snapshot(args.snapshot_id)
    elif args.command == "activity":
        list_activity(args.limit)
    elif args.command == "content-plan":
        content_plan(args.search_console, args.weeks, args.per_week)
    elif args.command == "draft":
        save_draft(args.input)
    elif args.command in ("dry-run", "preview-plan"):
        dry_run(args.input, args.id)
    elif args.command == "quality-check":
        payload = load_payload(args.input)
        validate_payload(payload)
        report = quality_audit(payload, args.id)
        print(json.dumps({"ok": report["ok"], "read_only": True, "quality": report}, ensure_ascii=False, separators=(",", ":")))
    else:
        save_draft(args.input, args.id)


if __name__ == "__main__":
    main()
