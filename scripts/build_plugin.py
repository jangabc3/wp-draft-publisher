#!/usr/bin/env python3
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "wp-draft-publisher-bridge"
SOURCE = ROOT / "wordpress-plugin" / PLUGIN_NAME
DIST = ROOT / "dist"
ARCHIVE = DIST / f"{PLUGIN_NAME}.zip"


def main():
    if not SOURCE.is_dir():
        raise SystemExit(f"Plugin source not found: {SOURCE}")
    DIST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for source in sorted(path for path in SOURCE.rglob("*") if path.is_file()):
            relative = source.relative_to(SOURCE).as_posix()
            target.write(source, f"{PLUGIN_NAME}/{relative}")
    print(json.dumps({"ok": True, "path": str(ARCHIVE), "bytes": ARCHIVE.stat().st_size}))


if __name__ == "__main__":
    main()
