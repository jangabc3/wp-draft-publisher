#!/usr/bin/env python3
"""Parse repository Python files without creating junction-sensitive .pyc files."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures = []
    for directory_name in ("scripts", "tests"):
        for path in sorted((ROOT / directory_name).rglob("*.py")):
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError, UnicodeError) as error:
                failures.append(f"{path.relative_to(ROOT)}: {error}")
    if failures:
        print("\n".join(failures))
        return 1
    print("[OK] Python syntax is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
