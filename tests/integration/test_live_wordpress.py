#!/usr/bin/env python3
"""Destructive integration tests for the disposable Docker WordPress site."""

import argparse
import base64
import importlib.util
import io
import json
import os
import ssl
import tempfile
import time
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from urllib.error import URLError
from urllib.request import HTTPSHandler, build_opener


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts" / "wordpress.py"
SPEC = importlib.util.spec_from_file_location("wpdp_live", MODULE)
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


def configure_client():
    ca_file = os.environ["WPDP_TEST_CA_FILE"]
    context = ssl.create_default_context(cafile=ca_file)
    wordpress.OPEN_URL = build_opener(wordpress.NoRedirectHandler(), HTTPSHandler(context=context)).open
    wordpress.SITE = os.environ["IK_WP_SITE_URL"].rstrip("/")
    wordpress.USER = os.environ["IK_WP_USERNAME"]
    wordpress.PASSWORD = os.environ["IK_WP_APP_PASSWORD"]


def call_json(function, *args):
    output = io.StringIO()
    try:
        with redirect_stdout(output):
            function(*args)
    except SystemExit as exc:
        raise AssertionError(output.getvalue()) from exc
    return json.loads(output.getvalue())


class LiveWordPressBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_client()
        cls.temporary = tempfile.TemporaryDirectory(prefix="wpdp-live-")
        cls.image = Path(cls.temporary.name) / "pixel.png"
        cls.image.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        ))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def payload(self, slug, title="통합 테스트 글 작성과 검증 방법", provider="auto"):
        return {
            "title": title,
            "slug": slug,
            "excerpt": "실제 WordPress REST API에서 글과 이미지, 분류, SEO 저장 과정을 확인하는 통합 테스트입니다.",
            "content": (
                "<p>통합 테스트 글 작성 과정을 실제 WordPress에서 확인합니다.</p>"
                "<h2>저장 순서</h2><p>글과 분류를 저장하고 서버 내용을 다시 확인합니다.</p>"
                "{{IMAGE_1}}"
                '<p><a href="https://www.gov.kr/">공식 참고자료</a></p>'
                "<h2>자주 묻는 질문</h2><h3>임시글만 저장되나요?</h3><p>네, 공개 상태로 변경하지 않습니다.</p>"
            ),
            "category_names": ["통합 테스트"],
            "tag_names": ["REST API"],
            "featured_image": {"path": str(self.image.resolve()), "alt": "통합 테스트 대표 이미지"},
            "inline_images": [{"marker": "{{IMAGE_1}}", "path": str(self.image.resolve()), "alt": "통합 테스트 본문 이미지"}],
            "image_policy": {"minimum_total": 1, "minimum_inline": 1},
            "seo": {
                "provider": provider,
                "title": title,
                "description": "실제 WordPress 환경에서 임시글, 이미지, 분류, SEO 정보가 안전하게 저장되고 다시 검증되는지 확인하는 통합 테스트입니다.",
                "focus_keyword": "WordPress 통합 테스트",
            },
            "quality": {"mode": "warn", "minimum_internal_links": 0, "minimum_official_links": 1},
        }

    def payload_file(self, value):
        path = Path(self.temporary.name) / f"{uuid.uuid4().hex}.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path


class CoreIntegrationTests(LiveWordPressBase):
    def test_full_draft_recovery_concurrency_and_network_flow(self):
        doctor = call_json(wordpress.doctor)
        self.assertTrue(doctor["ok"], doctor)
        self.assertTrue(doctor["checks"]["bridge"]["ok"])
        self.assertTrue(doctor["checks"]["bridge"]["optimistic_locking"])
        self.assertTrue(doctor["checks"]["bridge"]["snapshots"])
        self.assertEqual(doctor["checks"]["bridge"]["active_seo_provider"], "wordpress")

        slug = "wpdp-live-" + uuid.uuid4().hex[:12]
        original = self.payload(slug)
        original_path = self.payload_file(original)
        preview = call_json(wordpress.dry_run, original_path)
        self.assertFalse(preview["would_mutate"])
        self.assertEqual(preview["plan"]["operation"], "create_draft")
        self.assertEqual(preview["plan"]["safeguards"]["result_status"], "draft")
        self.assertEqual(preview["plan"]["quality"]["status"], "passed")
        created = call_json(wordpress.save_draft, original_path)
        self.assertEqual(created["status"], "draft")
        self.assertEqual(created["verification_status"], "verified")
        self.assertEqual(created["quality_status"], "passed")
        self.assertEqual(created["seo_provider"], "wordpress")
        self.assertGreaterEqual(created["media_count"], 1)
        post_id = created["id"]

        post = wordpress.api("GET", f"posts/{post_id}", query={"context": "edit"})
        self.assertEqual(post["status"], "draft")
        self.assertTrue(post["featured_media"])
        self.assertTrue(post["categories"])
        self.assertTrue(post["tags"])
        self.assertIn("wp-block-image", post["content"]["raw"])
        self.assertIn("공식 참고자료", post["content"]["raw"])

        updated_payload = self.payload(slug, "수정된 통합 테스트 글 작성과 검증 방법")
        updated_path = self.payload_file(updated_payload)
        update_preview = call_json(wordpress.dry_run, updated_path, post_id)
        self.assertFalse(update_preview["would_mutate"])
        self.assertEqual(update_preview["plan"]["operation"], "update_draft")
        self.assertEqual(update_preview["plan"]["target_post_id"], post_id)
        updated = call_json(wordpress.save_draft, updated_path, post_id)
        self.assertEqual(updated["action"], "updated_draft")
        self.assertIsInstance(updated["snapshot_id"], int)
        restored = call_json(wordpress.restore_snapshot, updated["snapshot_id"])
        self.assertTrue(restored["ok"])
        after_restore = wordpress.api("GET", f"posts/{post_id}", query={"context": "edit", "_fields": "id,title,status"})
        self.assertEqual(after_restore["title"]["raw"], original["title"])

        stale = wordpress.assert_draft_post(post_id)
        # WordPress modified_gmt has one-second precision. Cross a second boundary
        # so the live optimistic-locking assertion cannot become timing-dependent.
        time.sleep(1.1)
        wordpress.api("POST", f"posts/{post_id}", {"title": "다른 사용자가 수정한 제목"})
        stale_output = io.StringIO()
        with redirect_stdout(stale_output), self.assertRaises(SystemExit):
            wordpress.assert_draft_post(post_id, stale["modified_gmt"])
        self.assertEqual(json.loads(stale_output.getvalue())["error"], "post_changed_since_read")
        guarded = wordpress.api(
            "POST", f"posts/{post_id}", {"title": "오래된 자동화 수정"},
            headers={"X-WPDP-Draft-Only": "1", "X-WPDP-Expected-Modified-GMT": stale["modified_gmt"]},
            soft=True,
        )
        self.assertEqual(guarded.get("_error"), "wordpress_http_409")

        uncertain_slug = "wpdp-uncertain-" + uuid.uuid4().hex[:12]
        uncertain_payload = self.payload(uncertain_slug, "응답 단절 복구 통합 테스트 안내")
        real_open = wordpress.OPEN_URL
        dropped = {"done": False}

        def drop_first_create(request, *args, **kwargs):
            if request.get_method() == "POST" and request.full_url.endswith("/wp-json/wp/v2/posts") and not dropped["done"]:
                dropped["done"] = True
                response = real_open(request, *args, **kwargs)
                response.read()
                response.close()
                raise URLError("simulated response loss after server commit")
            return real_open(request, *args, **kwargs)

        wordpress.OPEN_URL = drop_first_create
        try:
            recovered = call_json(wordpress.save_draft, self.payload_file(uncertain_payload))
        finally:
            wordpress.OPEN_URL = real_open
        self.assertTrue(dropped["done"])
        self.assertEqual(recovered["recovery_status"], "recovered_after_uncertain_response")
        matches = wordpress.find_posts_by_slug(uncertain_slug)
        self.assertEqual(len(matches), 1)

        plan = call_json(wordpress.content_plan, None, 2, 1)
        self.assertTrue(plan["read_only"])
        self.assertFalse(plan["would_publish"])
        self.assertGreaterEqual(plan["inventory"]["posts"], 2)
        self.assertTrue(any(item["name"] == "통합 테스트" for item in plan["inventory"]["categories"]))


class RankMathIntegrationTests(LiveWordPressBase):
    def test_rank_math_values_are_saved_and_read_back(self):
        doctor = call_json(wordpress.doctor)
        self.assertIn("rank-math", doctor["checks"]["bridge"]["seo_providers"])
        self.assertEqual(doctor["checks"]["bridge"]["active_seo_provider"], "rank-math")
        slug = "wpdp-rank-math-" + uuid.uuid4().hex[:12]
        value = self.payload(slug, "Rank Math SEO 통합 저장 테스트", "rank-math")
        created = call_json(wordpress.save_draft, self.payload_file(value))
        self.assertEqual(created["seo_status"], "saved")
        self.assertEqual(created["seo_provider"], "rank-math")
        saved = wordpress.get_saved_seo(created["id"], "rank-math")
        self.assertEqual(saved["provider"], "rank-math")
        self.assertEqual(saved["title"], value["seo"]["title"])
        self.assertEqual(saved["description"], value["seo"]["description"])
        self.assertEqual(saved["focus_keyword"], value["seo"]["focus_keyword"])


class SeoProviderIntegrationTests(LiveWordPressBase):
    provider = "wordpress"

    def test_provider_values_are_saved_and_read_back(self):
        doctor = call_json(wordpress.doctor)
        if self.provider == "wordpress":
            self.assertEqual(doctor["checks"]["bridge"]["seo_providers"], [])
            requested = "none"
        else:
            self.assertIn(self.provider, doctor["checks"]["bridge"]["seo_providers"])
            requested = self.provider
        slug = "wpdp-seo-" + self.provider + "-" + uuid.uuid4().hex[:10]
        value = self.payload(slug, self.provider + " SEO 통합 저장 테스트", requested)
        created = call_json(wordpress.save_draft, self.payload_file(value))
        self.assertEqual(created["seo_provider"], self.provider)
        saved = wordpress.get_saved_seo(created["id"], self.provider)
        self.assertEqual(saved["provider"], self.provider)
        self.assertEqual(saved["title"], value["seo"]["title"] if self.provider != "wordpress" else value["title"])
        self.assertEqual(saved["description"], value["seo"]["description"] if self.provider != "wordpress" else value["excerpt"])
        if self.provider != "wordpress":
            self.assertEqual(saved["focus_keyword"], value["seo"]["focus_keyword"])


class MultipleSeoIntegrationTests(LiveWordPressBase):
    def test_all_plugins_are_detected_and_explicit_selection_wins(self):
        doctor = call_json(wordpress.doctor)
        providers = doctor["checks"]["bridge"]["seo_providers"]
        self.assertEqual(providers, ["rank-math", "yoast", "aioseo"])
        self.assertEqual(doctor["checks"]["bridge"]["active_seo_provider"], "rank-math")
        for provider in providers:
            slug = "wpdp-multi-" + provider + "-" + uuid.uuid4().hex[:8]
            value = self.payload(slug, provider + " 복수 SEO 선택 테스트", provider)
            created = call_json(wordpress.save_draft, self.payload_file(value))
            self.assertEqual(created["seo_provider"], provider)
            self.assertEqual(wordpress.get_saved_seo(created["id"], provider)["provider"], provider)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=("core", "rank-math", "seo-provider", "multiple-seo"), required=True)
    parser.add_argument("--provider", choices=("wordpress", "yoast", "aioseo"))
    args = parser.parse_args()
    if args.scenario == "core":
        case = CoreIntegrationTests
    elif args.scenario == "rank-math":
        case = RankMathIntegrationTests
    elif args.scenario == "multiple-seo":
        case = MultipleSeoIntegrationTests
    else:
        if not args.provider:
            parser.error("--provider is required for seo-provider")
        SeoProviderIntegrationTests.provider = args.provider
        case = SeoProviderIntegrationTests
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(case)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
