import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "wordpress.py"
SPEC = importlib.util.spec_from_file_location("wp_draft_quality", MODULE)
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


def payload():
    return {
        "title": "자동차 환급금 조회 방법과 신청 절차",
        "slug": "car-refund-guide",
        "excerpt": "자동차 환급금 조회와 신청 절차를 설명합니다.",
        "content": (
            '<p>자동차 환급금 조회 방법을 설명합니다.</p>'
            '<h2>조회 방법</h2><p>순서대로 확인하세요.</p>{{IMAGE_1}}'
            '<p><a href="https://example.test/older-guide/">관련 글</a></p>'
            '<p><a href="https://www.gov.kr/">정부24 공식 안내</a></p>'
            '<h2>자주 묻는 질문</h2><h3>누가 신청할 수 있나요?</h3><p>조건을 확인하세요.</p>'
        ),
        "featured_image": {"media_id": 10, "alt": "자동차 환급금 조회 안내"},
        "inline_images": [{"marker": "{{IMAGE_1}}", "media_id": 11, "alt": "조회 단계"}],
        "category_names": ["금융"],
        "tag_names": ["환급금"],
        "seo": {
            "provider": "auto",
            "title": "자동차 환급금 조회 방법과 신청 절차",
            "description": "자동차 환급금 조회 대상과 은행별 확인 방법, 신청할 때 필요한 내용을 순서대로 정리했습니다. 공식 안내와 함께 놓치기 쉬운 조건을 확인하세요.",
            "focus_keyword": "자동차 환급금 조회",
        },
    }


class LocalQualityTests(unittest.TestCase):
    def test_complete_article_passes_with_expected_checks(self):
        report = wordpress.quality.local_report(payload(), "https://example.test")
        self.assertTrue(report["ok"])
        self.assertTrue(report["checks"]["heading_order"])
        self.assertEqual(report["checks"]["internal_links_found"], 1)
        self.assertEqual(report["checks"]["official_links_found"], 1)
        self.assertIn(report["display"]["status"], ("passed", "needs_review"))
        self.assertTrue(report["display"]["can_save"])

    def test_bad_heading_and_missing_alt_are_blocking_errors(self):
        value = payload()
        value["content"] = '<h1>중복 H1</h1><h3>건너뛴 제목</h3><img src="x.jpg">'
        report = wordpress.quality.local_report(value, "https://example.test")
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("body_h1", codes)
        self.assertIn("heading_without_h2", codes)
        self.assertIn("image_alt_missing", codes)
        self.assertFalse(report["ok"])

    def test_strict_mode_blocks_recommendation_warnings(self):
        value = payload()
        value["quality"] = {"mode": "strict", "minimum_internal_links": 3}
        report = wordpress.quality.local_report(value, "https://example.test")
        self.assertFalse(report["ok"])
        self.assertIn("internal_links_below_minimum", {item["code"] for item in report["warnings"]})

    def test_quality_policy_rejects_unknown_or_invalid_values(self):
        for configured in ({"mode": "maybe"}, {"title_min": True}, {"unknown": 1}, {"official_domains": "gov.kr"}):
            value = payload()
            value["quality"] = configured
            with self.subTest(configured=configured), redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                wordpress.validate_payload(value)

    def test_time_sensitive_article_requires_current_official_source_records(self):
        value = payload()
        value["freshness"] = {"time_sensitive": True, "as_of": "2026-10-20", "effective_year": 2026}
        value["source_records"] = [{
            "url": "https://www.gov.kr/", "title": "정부 공식 안내", "publisher": "정부24",
            "checked_at": "2026-10-20", "official": True, "effective_year": 2026,
            "claims": {"지원 대상": "만 19세 이상"},
        }]
        wordpress.validate_payload(value)
        report = wordpress.quality.local_report(value, "https://example.test")
        self.assertTrue(report["ok"])
        self.assertEqual(report["checks"]["official_source_records"], 1)
        self.assertEqual(report["freshness"]["latest_checked_at"], "2026-10-20")

    def test_conflicting_or_expired_official_facts_block_saving(self):
        value = payload()
        value["freshness"] = {"time_sensitive": True, "as_of": "2026-10-20", "effective_year": 2026}
        value["source_records"] = [
            {"url": "https://www.gov.kr/", "title": "안내 1", "publisher": "정부24", "checked_at": "2026-10-20", "official": True, "effective_year": 2026, "claims": {"소득 기준": "100%"}},
            {"url": "https://example.go.kr/notice", "title": "안내 2", "publisher": "공공기관", "checked_at": "2026-10-20", "official": True, "effective_year": 2026, "expires_on": "2026-09-30", "claims": {"소득 기준": "120%"}},
        ]
        report = wordpress.quality.local_report(value, "https://example.test")
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("conflicting_source_claim", codes)
        self.assertIn("source_expired", codes)
        self.assertFalse(report["display"]["can_save"])
        self.assertTrue(all("suggested_fix" in item for item in report["display"]["issues"]))

    def test_invalid_source_metadata_is_rejected_before_network(self):
        value = payload()
        value["source_records"] = [{"url": "http://example.test", "title": "Bad", "publisher": "Test", "checked_at": "tomorrow"}]
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            wordpress.validate_payload(value)

    def test_safe_fixes_normalize_formatting_without_rewriting_facts(self):
        value = payload()
        value["title"] = "  " + value["title"] + "  "
        value["seo"]["description"] = "설명에   불필요한   공백"
        value["content"] += '<p><img src="x.jpg" alt="설명" width="900" style="width:900px;height:auto"></p>'
        fixed = wordpress.quality.apply_safe_fixes(value)
        self.assertEqual(fixed["title"], value["title"].strip())
        self.assertEqual(fixed["seo"]["description"], "설명에 불필요한 공백")
        self.assertNotIn('width="900"', fixed["content"])
        self.assertNotIn("width:900px", fixed["content"])
        self.assertGreaterEqual(len(fixed["_wpdp_auto_fixes"]), 3)
        self.assertIn("조건을 확인하세요", fixed["content"])


class RemoteQualityTests(unittest.TestCase):
    def test_internal_link_and_duplicate_title_checks_are_read_only(self):
        requests = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            requests.append((method, endpoint, query))
            if endpoint == "posts" and query.get("slug"):
                return []
            if endpoint == "pages":
                return []
            if endpoint == "posts" and query.get("search"):
                return [{"id": 9, "title": {"raw": payload()["title"]}, "slug": "duplicate"}]
            return []

        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(wordpress, "SITE", "https://example.test"):
            report = wordpress.quality_audit(payload())
        codes = {item["code"] for item in report["warnings"]}
        self.assertIn("broken_internal_links", codes)
        self.assertIn("similar_existing_posts", codes)
        self.assertTrue(all(item[0] == "GET" for item in requests))


class SeoProviderTests(unittest.TestCase):
    def test_auto_provider_uses_bridge_detection(self):
        plan = wordpress.seo_plan(payload(), {"seo_providers": ["yoast"], "active_seo_provider": "yoast"})
        self.assertEqual(plan["selected_provider"], "yoast")
        self.assertFalse(plan["fallback"])

    def test_no_plugin_falls_back_to_wordpress_title_and_excerpt(self):
        plan = wordpress.seo_plan(payload(), {"seo_providers": [], "active_seo_provider": "wordpress"})
        self.assertEqual(plan["selected_provider"], "wordpress")
        self.assertTrue(plan["fallback"])

    def test_registered_legacy_meta_does_not_imply_rank_math_is_active(self):
        plan = wordpress.seo_plan(
            payload(),
            {
                "seo_providers": [],
                "active_seo_provider": "wordpress",
                "rank_math_meta": ["rank_math_title", "rank_math_description"],
            },
        )
        self.assertEqual(plan["selected_provider"], "wordpress")

    def test_bridge_saves_selected_provider(self):
        value = payload()
        value["seo"]["provider"] = "aioseo"
        with patch.object(wordpress, "bridge_status", return_value={"seo_providers": ["aioseo"], "active_seo_provider": "aioseo"}), patch.object(
            wordpress, "rest_api", return_value={"ok": True, "provider": "aioseo", "title_saved": True}
        ) as request:
            result = wordpress.save_seo(42, value, "operation-1")
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["provider"], "aioseo")
        self.assertEqual(request.call_args.args[:2], ("POST", "wp-draft-publisher/v1/posts/42/seo"))


if __name__ == "__main__":
    unittest.main()
