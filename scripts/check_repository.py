#!/usr/bin/env python3
"""Validate release-facing repository structure without external packages."""

import json
import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", "release", "__pycache__", ".runtime"}
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
REMOTE_SCHEMES = ("http://", "https://", "mailto:", "tel:", "codex:", "app:")


def source_files(suffix):
    return sorted(
        path for path in ROOT.rglob(f"*{suffix}")
        if path.is_file() and not any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts)
    )


def markdown_target(raw):
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1:value.index(">")]
    elif " " in value:
        value = value.split(" ", 1)[0]
    return unquote(value.split("#", 1)[0])


def check_markdown_links():
    problems = []
    for document in source_files(".md"):
        text = document.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            target = markdown_target(match.group(1))
            if not target or target.casefold().startswith(REMOTE_SCHEMES):
                continue
            if target.startswith("/"):
                problems.append(f"absolute local link: {document.relative_to(ROOT)} -> {target}")
                continue
            destination = (document.parent / target).resolve()
            try:
                destination.relative_to(ROOT.resolve())
            except ValueError:
                problems.append(f"link escapes repository: {document.relative_to(ROOT)} -> {target}")
                continue
            if not destination.exists():
                problems.append(f"missing link target: {document.relative_to(ROOT)} -> {target}")
    return problems


def check_json():
    problems = []
    for path in source_files(".json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(f"invalid JSON: {path.relative_to(ROOT)} ({exc})")
    return problems


def check_release_metadata():
    problems = []
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        problems.append(f"invalid VERSION: {version!r}")
    required_mentions = {
        ROOT / "README.md": f"Current project version: **{version}**",
        ROOT / "docs" / "INSTALL.md": f"wp-draft-publisher-v{version}.zip",
        ROOT / "docs" / "INSTALL.ko.md": f"wp-draft-publisher-v{version}.zip",
        ROOT / "docs" / f"RELEASE_NOTES_v{version}.md": f"# WP Draft Publisher v{version}",
    }
    for path, expected in required_mentions.items():
        if not path.is_file():
            problems.append(f"missing release file: {path.relative_to(ROOT)}")
        elif expected not in path.read_text(encoding="utf-8"):
            problems.append(f"version mismatch: {path.relative_to(ROOT)}")
    return problems


def scan():
    return check_markdown_links() + check_json() + check_release_metadata()


def main():
    problems = scan()
    if problems:
        raise SystemExit("Repository check failed:\n" + "\n".join(f"- {item}" for item in problems))
    print("Repository structure, local links, JSON, and release metadata passed.")


if __name__ == "__main__":
    main()
