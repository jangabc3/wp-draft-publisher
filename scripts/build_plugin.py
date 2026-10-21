#!/usr/bin/env python3
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "wp-draft-publisher-bridge"
PLUGIN_NAME = "draft-publisher-rest-bridge"
SOURCE = ROOT / "wordpress-plugin" / SOURCE_NAME
DIST = ROOT / "dist"
ARCHIVE = DIST / f"{PLUGIN_NAME}.zip"
FIXED_TIMESTAMP = (2020, 1, 1, 0, 0, 0)
TEXT_SUFFIXES = {".md", ".php", ".txt"}


def packaged_bytes(source):
    value = source.read_bytes()
    if source.suffix.casefold() in TEXT_SUFFIXES:
        return value.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return value


def main():
    if not SOURCE.is_dir():
        raise SystemExit(f"Plugin source not found: {SOURCE}")
    DIST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for source in sorted(path for path in SOURCE.rglob("*") if path.is_file()):
            relative = source.relative_to(SOURCE).as_posix()
            info = zipfile.ZipInfo(f"{PLUGIN_NAME}/{relative}", FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            target.writestr(info, packaged_bytes(source))
    print(json.dumps({"ok": True, "path": str(ARCHIVE), "bytes": ARCHIVE.stat().st_size}))


if __name__ == "__main__":
    main()
