#!/usr/bin/env python3
"""Deterministic, dependency-free article quality checks."""

import re
from copy import deepcopy
from datetime import date, timedelta
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.parse import urlsplit


DEFAULTS = {
    "mode": "warn",
    "title_min": 15,
    "title_max": 65,
    "meta_min": 70,
    "meta_max": 170,
    "minimum_internal_links": 1,
    "minimum_official_links": 1,
    "max_paragraphs_without_image": 6,
    "require_faq": False,
    "check_internal_links": True,
    "check_duplicate_titles": True,
    "official_domains": [],
    "require_source_records": False,
    "source_max_age_days": 45,
}


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings = []
        self.links = []
        self.images = []
        self.tables = []
        self.paragraphs = 0
        self.events = []
        self._heading = None
        self._heading_text = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        tag = tag.lower()
        if re.fullmatch(r"h[1-6]", tag):
            self._heading = int(tag[1])
            self._heading_text = []
        elif tag == "a":
            self.links.append(values.get("href", "").strip())
        elif tag == "img":
            self.images.append(values)
            self.events.append("image")
        elif tag == "p":
            self.paragraphs += 1
            self.events.append("paragraph")
        elif tag == "table":
            self.tables.append(values)

    def handle_endtag(self, tag):
        if self._heading and tag.lower() == f"h{self._heading}":
            text = " ".join("".join(self._heading_text).split())
            self.headings.append((self._heading, text))
            self.events.append(f"h{self._heading}")
            self._heading = None
            self._heading_text = []

    def handle_data(self, data):
        if self._heading:
            self._heading_text.append(data)


def policy(payload):
    configured = payload.get("quality", {}) or {}
    return {**DEFAULTS, **configured}


def validate_policy(payload):
    configured = payload.get("quality", {})
    if configured is None:
        return
    if not isinstance(configured, dict):
        raise ValueError("quality")
    allowed = set(DEFAULTS)
    if set(configured) - allowed:
        raise ValueError("quality." + sorted(set(configured) - allowed)[0])
    if configured.get("mode", "warn") not in ("warn", "strict"):
        raise ValueError("quality.mode")
    for key in (
        "title_min", "title_max", "meta_min", "meta_max",
        "minimum_internal_links", "minimum_official_links", "max_paragraphs_without_image", "source_max_age_days",
    ):
        value = configured.get(key, DEFAULTS[key])
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"quality.{key}")
    for key in ("require_faq", "check_internal_links", "check_duplicate_titles", "require_source_records"):
        if not isinstance(configured.get(key, DEFAULTS[key]), bool):
            raise ValueError(f"quality.{key}")
    domains = configured.get("official_domains", [])
    if not isinstance(domains, list) or any(not isinstance(item, str) or not item.strip() for item in domains):
        raise ValueError("quality.official_domains")
    merged = policy(payload)
    if merged["title_min"] > merged["title_max"] or merged["meta_min"] > merged["meta_max"]:
        raise ValueError("quality.range")


def parse_iso_date(value, field):
    if not isinstance(value, str):
        raise ValueError(field)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(field) from exc


def validate_sources(payload):
    freshness = payload.get("freshness", {}) or {}
    if not isinstance(freshness, dict):
        raise ValueError("freshness")
    allowed = {"time_sensitive", "as_of", "effective_year"}
    if set(freshness) - allowed:
        raise ValueError("freshness." + sorted(set(freshness) - allowed)[0])
    if not isinstance(freshness.get("time_sensitive", False), bool):
        raise ValueError("freshness.time_sensitive")
    if "as_of" in freshness:
        parse_iso_date(freshness["as_of"], "freshness.as_of")
    if "effective_year" in freshness:
        year = freshness["effective_year"]
        if isinstance(year, bool) or not isinstance(year, int) or not 2000 <= year <= 2200:
            raise ValueError("freshness.effective_year")
    records = payload.get("source_records", [])
    if not isinstance(records, list):
        raise ValueError("source_records")
    for index, record in enumerate(records):
        field = f"source_records[{index}]"
        if not isinstance(record, dict):
            raise ValueError(field)
        allowed_record = {"url", "title", "publisher", "checked_at", "official", "published_at", "effective_year", "expires_on", "claims"}
        if set(record) - allowed_record:
            raise ValueError(field + "." + sorted(set(record) - allowed_record)[0])
        for key in ("url", "title", "publisher", "checked_at"):
            if not isinstance(record.get(key), str) or not record[key].strip():
                raise ValueError(field + "." + key)
        parsed = urlsplit(record["url"])
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError(field + ".url")
        parse_iso_date(record["checked_at"], field + ".checked_at")
        if not isinstance(record.get("official", False), bool):
            raise ValueError(field + ".official")
        for key in ("published_at", "expires_on"):
            if key in record:
                parse_iso_date(record[key], field + "." + key)
        if "effective_year" in record:
            year = record["effective_year"]
            if isinstance(year, bool) or not isinstance(year, int) or not 2000 <= year <= 2200:
                raise ValueError(field + ".effective_year")
        claims = record.get("claims", {})
        if not isinstance(claims, dict) or any(not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip() for key, value in claims.items()):
            raise ValueError(field + ".claims")


def issue(code, message, **details):
    value = {"code": code, "message": message}
    if details:
        value["details"] = details
    return value


def normalized_title(value):
    return " ".join(re.findall(r"[0-9a-zA-Z가-힣]+", (value or "").casefold()))


def title_similarity(left, right):
    return SequenceMatcher(None, normalized_title(left), normalized_title(right)).ratio()


def suggested_fix(code):
    fixes = {
        "title_length": "제목을 권장 글자 수 안에서 핵심 검색어가 보이도록 수정하세요.",
        "meta_description_length": "메타 설명을 권장 길이에 맞춰 한 문단으로 다듬으세요.",
        "official_sources_below_minimum": "공식 기관의 HTTPS 원문 링크를 추가하세요.",
        "source_records_missing": "출처 URL, 기관명, 확인 날짜를 source_records에 기록하세요.",
        "source_check_stale": "원문을 다시 열어 현재 조건을 확인하고 checked_at을 갱신하세요.",
        "source_not_linked_in_content": "독자가 확인할 수 있도록 해당 출처를 본문의 참고자료에 연결하세요.",
        "source_year_mismatch": "시행 연도와 자료의 적용 연도를 다시 확인하세요.",
        "source_expired": "마감된 자료를 제거하거나 현재 접수 공고로 교체하세요.",
        "conflicting_source_claim": "서로 다른 값을 임의로 선택하지 말고 최신 공식 원문으로 충돌을 해결하세요.",
        "no_official_source_record": "공식 기관이 직접 제공한 자료를 한 개 이상 추가하세요.",
        "internal_links_below_minimum": "실제로 존재하는 관련 글을 내부 링크로 추가하세요.",
    }
    return fixes.get(code, "표시된 항목을 확인하고 저장 전에 수정하세요.")


def add_display_summary(report):
    issues = []
    for severity, values in (("blocking", report.get("errors", [])), ("recommendation", report.get("warnings", []))):
        for value in values:
            issues.append({
                "severity": severity,
                "code": value.get("code"),
                "message": value.get("message"),
                "suggested_fix": suggested_fix(value.get("code")),
                "auto_fixable": False,
            })
    checks = report.get("checks", {})
    boolean_checks = [value for value in checks.values() if isinstance(value, bool)]
    passed = sum(1 for value in boolean_checks if value)
    status = "blocked" if report.get("errors") or (report.get("mode") == "strict" and report.get("warnings")) else ("needs_review" if report.get("warnings") else "passed")
    report["display"] = {
        "status": status,
        "headline": f"품질검사 {passed}/{len(boolean_checks)}개 핵심 항목 통과",
        "score": report.get("score"),
        "blocking_count": len(report.get("errors", [])),
        "recommendation_count": len(report.get("warnings", [])),
        "issues": issues,
        "can_save": bool(report.get("ok")),
    }
    return report


def apply_safe_fixes(payload):
    """Apply only formatting fixes that do not invent or remove factual meaning."""
    value = deepcopy(payload)
    fixes = []
    for field in ("title", "slug", "excerpt"):
        if isinstance(value.get(field), str):
            cleaned = value[field].strip()
            if cleaned != value[field]:
                value[field] = cleaned
                fixes.append({"code": "trim_whitespace", "field": field})
    seo = value.get("seo")
    if isinstance(seo, dict):
        for field in ("title", "description", "focus_keyword"):
            if isinstance(seo.get(field), str):
                cleaned = " ".join(seo[field].split())
                if cleaned != seo[field]:
                    seo[field] = cleaned
                    fixes.append({"code": "normalize_seo_whitespace", "field": "seo." + field})

    def repair_image(match):
        original = match.group(0)
        repaired = re.sub(r"\s+width\s*=\s*(['\"])\d+\1", "", original, flags=re.I)
        repaired = re.sub(r"width\s*:\s*\d+(?:px|rem|em)\s*;?", "", repaired, flags=re.I)
        if repaired != original:
            fixes.append({"code": "remove_fixed_image_width", "field": "content"})
        return repaired

    if isinstance(value.get("content"), str):
        value["content"] = re.sub(r"<img\b[^>]*>", repair_image, value["content"], flags=re.I)
    if fixes:
        value["_wpdp_auto_fixes"] = fixes
    return value


def local_report(payload, site_url=""):
    configured = policy(payload)
    parser = ArticleParser()
    content_for_checks = payload.get("content", "")
    for item in payload.get("inline_images", []):
        marker = item.get("marker")
        if marker:
            alt = (item.get("alt") or "").replace('"', "&quot;")
            content_for_checks = content_for_checks.replace(marker, f'<img alt="{alt}">', 1)
    parser.feed(content_for_checks)
    errors, warnings = [], []
    title = payload.get("title", "").strip()
    seo = payload.get("seo", {})
    description = seo.get("description", "").strip()
    focus = seo.get("focus_keyword", "").strip().casefold()

    if not configured["title_min"] <= len(title) <= configured["title_max"]:
        warnings.append(issue("title_length", "제목 길이가 권장 범위를 벗어났습니다.", characters=len(title), minimum=configured["title_min"], maximum=configured["title_max"]))
    if not configured["meta_min"] <= len(description) <= configured["meta_max"]:
        warnings.append(issue("meta_description_length", "메타 설명 길이가 권장 범위를 벗어났습니다.", characters=len(description), minimum=configured["meta_min"], maximum=configured["meta_max"]))
    if focus and focus not in (seo.get("title", "") + " " + title).casefold():
        warnings.append(issue("focus_keyword_missing_from_title", "포커스 키워드가 제목에 정확히 포함되지 않았습니다."))
    opening = re.sub(r"<[^>]+>", " ", payload.get("content", ""))[:600].casefold()
    if focus and focus not in opening:
        warnings.append(issue("focus_keyword_missing_from_opening", "포커스 키워드가 본문 도입부에 없습니다."))

    last_level = 1
    seen_h2 = False
    for level, text in parser.headings:
        if level == 1:
            errors.append(issue("body_h1", "본문에는 H1을 넣지 마세요. 글 제목이 H1 역할을 합니다.", heading=text))
        if level == 2:
            seen_h2 = True
        if level >= 3 and not seen_h2:
            errors.append(issue("heading_without_h2", "H2보다 먼저 하위 제목이 사용됐습니다.", heading=text, level=level))
        if level > last_level + 1:
            errors.append(issue("heading_level_skipped", "제목 단계가 건너뛰었습니다.", heading=text, previous_level=last_level, level=level))
        last_level = level

    faq_indexes = [i for i, (_, text) in enumerate(parser.headings) if re.search(r"자주\s*묻는\s*질문|faq", text, re.I)]
    if configured["require_faq"] and not faq_indexes:
        warnings.append(issue("faq_missing", "설정에서 요구한 FAQ 섹션이 없습니다."))
    for index in faq_indexes:
        level = parser.headings[index][0]
        questions = [item for item in parser.headings[index + 1:] if item[0] > level]
        if not questions:
            errors.append(issue("faq_questions_missing", "FAQ 제목 아래에 질문 제목이 없습니다."))

    host = urlsplit(site_url).hostname if site_url else ""
    internal_links, external_links, official_links = [], [], []
    official_domains = [item.strip().casefold().lstrip(".") for item in configured["official_domains"]]
    for href in parser.links:
        parsed = urlsplit(href)
        if not href or href.startswith(("#", "mailto:", "tel:")):
            continue
        if href.startswith("/") or (host and parsed.hostname == host):
            internal_links.append(href)
        elif parsed.scheme == "https" and parsed.hostname:
            external_links.append(href)
            domain = parsed.hostname.casefold()
            if domain.endswith(".go.kr") or domain == "gov.kr" or domain.endswith(".gov.kr") or domain.endswith(".gov") or any(domain == allowed or domain.endswith("." + allowed) for allowed in official_domains):
                official_links.append(href)
        elif parsed.scheme == "http":
            warnings.append(issue("insecure_external_link", "HTTPS가 아닌 외부 링크가 있습니다.", url=href))
    if len(set(internal_links)) < configured["minimum_internal_links"]:
        warnings.append(issue("internal_links_below_minimum", "내부 링크 수가 설정한 최소값보다 적습니다.", found=len(set(internal_links)), minimum=configured["minimum_internal_links"]))
    if len(set(official_links)) < configured["minimum_official_links"]:
        warnings.append(issue("official_sources_below_minimum", "확인 가능한 공식 출처 링크 수가 설정한 최소값보다 적습니다.", found=len(set(official_links)), minimum=configured["minimum_official_links"], configured_domains=official_domains))

    freshness = payload.get("freshness", {}) or {}
    records = payload.get("source_records", [])
    as_of = parse_iso_date(freshness.get("as_of", date.today().isoformat()), "freshness.as_of")
    time_sensitive = freshness.get("time_sensitive", False)
    if (time_sensitive or configured["require_source_records"]) and not records:
        errors.append(issue("source_records_missing", "날짜에 민감한 글에는 확인 가능한 출처 기록이 필요합니다."))
    if time_sensitive and records and not any(record.get("official") for record in records):
        errors.append(issue("no_official_source_record", "날짜에 민감한 글에는 공식 출처가 한 개 이상 필요합니다."))
    claim_values = {}
    stale_count = 0
    for record in records:
        checked = parse_iso_date(record["checked_at"], "source_records.checked_at")
        if checked > as_of:
            errors.append(issue("source_checked_in_future", "출처 확인 날짜가 기준일보다 미래입니다.", url=record["url"], checked_at=record["checked_at"]))
        elif (as_of - checked).days > configured["source_max_age_days"]:
            stale_count += 1
            warnings.append(issue("source_check_stale", "출처를 확인한 지 오래되어 최신 내용을 다시 확인해야 합니다.", url=record["url"], checked_at=record["checked_at"], maximum_days=configured["source_max_age_days"]))
        if record.get("expires_on") and parse_iso_date(record["expires_on"], "source_records.expires_on") < as_of:
            errors.append(issue("source_expired", "마감일이 지난 자료가 현재 정보로 사용됐습니다.", url=record["url"], expires_on=record["expires_on"]))
        expected_year = freshness.get("effective_year")
        if expected_year and record.get("effective_year") and record["effective_year"] != expected_year:
            errors.append(issue("source_year_mismatch", "자료의 적용 연도가 글의 기준 연도와 다릅니다.", url=record["url"], expected=expected_year, found=record["effective_year"]))
        if record["url"] not in payload.get("content", ""):
            warnings.append(issue("source_not_linked_in_content", "출처 기록의 URL이 본문에 연결되어 있지 않습니다.", url=record["url"]))
        for key, value in record.get("claims", {}).items():
            normalized_key = key.strip().casefold()
            claim_values.setdefault(normalized_key, {}).setdefault(value.strip(), []).append(record["url"])
    for key, values in claim_values.items():
        if len(values) > 1:
            errors.append(issue("conflicting_source_claim", "출처별 핵심 조건이 서로 달라 저장할 수 없습니다.", claim=key, values=values))

    gap = maximum_gap = 0
    for event in parser.events:
        if event == "paragraph":
            gap += 1
            maximum_gap = max(maximum_gap, gap)
        elif event == "image":
            gap = 0
    marker_count = len(payload.get("inline_images", []))
    if marker_count == 0 and parser.paragraphs > configured["max_paragraphs_without_image"]:
        warnings.append(issue("image_spacing", "긴 본문에 인라인 이미지가 없습니다.", paragraphs=parser.paragraphs))
    elif maximum_gap > configured["max_paragraphs_without_image"]:
        warnings.append(issue("image_spacing", "이미지 사이의 문단 간격이 너무 깁니다.", maximum_paragraphs=maximum_gap))
    for image in parser.images:
        if not image.get("alt", "").strip():
            errors.append(issue("image_alt_missing", "본문 이미지에 대체 텍스트가 없습니다."))
        style = image.get("style", "").replace(" ", "").casefold()
        if image.get("width") or re.search(r"width:\d+(px|rem|em)", style):
            warnings.append(issue("fixed_image_width", "고정 이미지 너비는 모바일 화면에서 넘칠 수 있습니다."))
    for table in parser.tables:
        style = table.get("style", "").replace(" ", "").casefold()
        if table.get("width") or "white-space:nowrap" in style or re.search(r"width:\d+(px|rem|em)", style):
            warnings.append(issue("table_mobile_overflow", "표에 모바일 넘침을 유발할 수 있는 고정 너비가 있습니다."))
        warnings.append(issue("table_responsive_preview", "표는 모바일 미리보기에서 가로 스크롤 또는 줄바꿈을 확인하세요."))

    blocking = bool(errors) or (configured["mode"] == "strict" and bool(warnings))
    score = max(0, 100 - len(errors) * 15 - len(warnings) * 4)
    result = {
        "ok": not blocking,
        "mode": configured["mode"],
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "heading_order": not any(item["code"].startswith(("body_h1", "heading_")) for item in errors),
            "image_alt": not any(item["code"] == "image_alt_missing" for item in errors),
            "faq_structure": not any(item["code"] == "faq_questions_missing" for item in errors),
            "internal_links_found": len(set(internal_links)),
            "official_links_found": len(set(official_links)),
            "external_links_found": len(set(external_links)),
            "inline_images": len(parser.images),
            "tables": len(parser.tables),
            "source_records": len(records),
            "official_source_records": sum(1 for record in records if record.get("official")),
            "stale_source_records": stale_count,
        },
        "internal_links": sorted(set(internal_links)),
        "freshness": {
            "time_sensitive": time_sensitive,
            "as_of": as_of.isoformat(),
            "effective_year": freshness.get("effective_year"),
            "latest_checked_at": max((record["checked_at"] for record in records), default=None),
            "next_review_due": (max((parse_iso_date(record["checked_at"], "source_records.checked_at") for record in records), default=as_of) + timedelta(days=configured["source_max_age_days"])).isoformat() if time_sensitive else None,
        },
    }
    result = add_display_summary(result)
    result["display"]["auto_fixes_applied"] = payload.get("_wpdp_auto_fixes", [])
    return result
