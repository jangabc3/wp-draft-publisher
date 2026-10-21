#!/usr/bin/env python3
"""Fail when public source files contain common secret material."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", "release", "__pycache__", ".runtime"}
SKIP_SUFFIXES = {".zip", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".pyc"}
FORBIDDEN_FILENAMES = {"credentials.json", ".env", "id_rsa", "id_ed25519"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Google verification token": re.compile(r"google-site-verification[^\n]{0,100}content=[\"'][^\"']+[\"']", re.I),
    "plaintext WordPress password environment value": re.compile(r"IK_WP_APP_PASSWORD\s*=\s*[^\s$%{][^\r\n]*"),
}


def scan():
    problems = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_PARTS for part in relative.parts) or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if path.name.lower() in FORBIDDEN_FILENAMES:
            problems.append(f"forbidden file: {relative.as_posix()}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                problems.append(f"{label}: {relative.as_posix()}")
    return problems


def main():
    problems = scan()
    if problems:
        raise SystemExit("Public release scan failed:\n" + "\n".join(f"- {item}" for item in problems))
    print("Public release scan passed.")


if __name__ == "__main__":
    main()
