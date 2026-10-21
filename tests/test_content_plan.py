import csv
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wpdp_content_plan", ROOT / "scripts" / "wordpress.py")
wordpress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wordpress)


class ContentPlanTests(unittest.TestCase):
    def export(self, rows):
        temporary = tempfile.NamedTemporaryFile(mode="w", dir=ROOT / "tests", suffix=".csv", encoding="utf-8", newline="", delete=False)
        writer = csv.DictWriter(temporary, fieldnames=["query", "page", "clicks", "impressions", "ctr", "position"])
        writer.writeheader()
        writer.writerows(rows)
        temporary.close()
        path = Path(temporary.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_read_only_plan_uses_inventory_and_search_performance(self):
        requests = []

        def fake_api(method, endpoint, data=None, headers=None, query=None, soft=False):
            requests.append((method, endpoint))
            if endpoint == "categories":
                return [{"id": 1, "name": "금융", "slug": "finance", "count": 1}, {"id": 2, "name": "여행", "slug": "travel", "count": 0}]
            return [
                {"id": 10, "title": {"raw": "ETF 초보 투자 방법"}, "slug": "etf-guide", "status": "publish", "link": "https://example.test/etf-guide/", "categories": [1], "modified_gmt": "2026-10-01T00:00:00"},
                {"id": 11, "title": {"raw": "ETF 초보 투자 방법 안내"}, "slug": "etf-guide-2", "status": "draft", "link": "https://example.test/?p=11", "categories": [1], "modified_gmt": "2026-10-02T00:00:00"},
            ]

        export = self.export([
            {"query": "ETF 초보 투자 방법", "page": "/etf-guide/", "clicks": 3, "impressions": 500, "ctr": "0.6%", "position": 9},
            {"query": "일본 여행 환전 수수료", "page": "", "clicks": 1, "impressions": 300, "ctr": "0.3%", "position": 14},
        ])
        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(wordpress, "SITE", "https://example.test"), redirect_stdout(output):
            wordpress.content_plan(str(export), 2, 1)
        result = json.loads(output.getvalue())
        self.assertTrue(result["read_only"])
        self.assertFalse(result["would_publish"])
        self.assertEqual(result["inventory"]["categories"][0]["name"], "여행")
        self.assertEqual(len(result["recommendations"]), 2)
        self.assertEqual(result["recommendations"][0]["action"], "update_existing")
        self.assertTrue(result["inventory"]["duplicate_title_groups"])
        self.assertTrue(all(method == "GET" for method, _ in requests))
        self.assertTrue(all(item["publish_status"] == "proposal_only" for item in result["schedule"]))

    def test_plan_without_export_reports_category_gaps(self):
        def fake_api(method, endpoint, **kwargs):
            return [{"id": 1, "name": "여행", "slug": "travel", "count": 0}] if endpoint == "categories" else []
        output = io.StringIO()
        with patch.object(wordpress, "api", side_effect=fake_api), patch.object(wordpress, "SITE", "https://example.test"), redirect_stdout(output):
            wordpress.content_plan(None, 4, 2)
        result = json.loads(output.getvalue())
        self.assertFalse(result["search_console"]["imported"])
        self.assertEqual(result["recommendations"], [])
        self.assertTrue(result["notes"])

    def test_invalid_metrics_are_rejected(self):
        export = self.export([{"query": "bad", "page": "", "clicks": "x", "impressions": 20, "ctr": "1%", "position": 3}])
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            wordpress.load_search_console_export(str(export))

    def test_duplicate_query_rows_are_aggregated(self):
        rows = [
            {"query": "ETF 사는 법", "page": "/one", "clicks": 1, "impressions": 100, "ctr": .01, "position": 10},
            {"query": "etf 사는 법", "page": "/two", "clicks": 2, "impressions": 200, "ctr": .01, "position": 20},
        ]
        aggregated = wordpress.aggregate_search_queries(rows)
        self.assertEqual(len(aggregated), 1)
        self.assertEqual(aggregated[0]["clicks"], 3)
        self.assertEqual(aggregated[0]["impressions"], 300)
        self.assertAlmostEqual(aggregated[0]["position"], 50 / 3)

    def test_inventory_paginates_until_a_short_page(self):
        calls = []

        def fake_api(method, endpoint, **kwargs):
            calls.append(kwargs["query"]["page"])
            return [{"id": index} for index in range(100)] if len(calls) == 1 else [{"id": 101}]

        with patch.object(wordpress, "api", side_effect=fake_api):
            result = wordpress.fetch_all_inventory("posts", {"context": "edit"})
        self.assertEqual(len(result), 101)
        self.assertEqual(calls, [1, 2])

    def test_korean_search_console_headers_and_thousands_are_supported(self):
        temporary = tempfile.NamedTemporaryFile(mode="w", dir=ROOT / "tests", suffix=".csv", encoding="utf-8", newline="", delete=False)
        writer = csv.DictWriter(temporary, fieldnames=["인기 검색어", "클릭수", "노출수", "CTR", "게재순위"])
        writer.writeheader()
        writer.writerow({"인기 검색어": "청년 지원금", "클릭수": "12", "노출수": "1,234", "CTR": "0.97%", "게재순위": "8.4"})
        temporary.close()
        path = Path(temporary.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        result = wordpress.load_search_console_export(str(path))
        self.assertEqual(result[0]["query"], "청년 지원금")
        self.assertEqual(result[0]["impressions"], 1234)
        self.assertAlmostEqual(result[0]["ctr"], .0097)

    def test_inventory_does_not_hide_a_later_page_failure(self):
        responses = [
            [{"id": index} for index in range(100)],
            {"_error": "wordpress_http_503", "_details": {"code": "maintenance"}},
        ]
        with patch.object(wordpress, "api", side_effect=responses), redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            wordpress.fetch_all_inventory("posts", {"context": "edit"})


if __name__ == "__main__":
    unittest.main()
