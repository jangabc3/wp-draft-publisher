#!/usr/bin/env python3
"""Build deterministic end-user release artifacts and checksums."""

import hashlib
import argparse
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
RELEASE_DIR = ROOT / "release"
PLUGIN_SOURCE = ROOT / "dist" / "draft-publisher-rest-bridge.zip"
PACKAGE_ROOT = "wp-draft-publisher"

TOP_LEVEL_FILES = {
    "VERSION", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "README.md",
    "README.ko.md", "SECURITY.md", "SKILL.md", "SUPPORT.md", "install.cmd",
    "install.ps1", "uninstall.ps1",
}
TOP_LEVEL_DIRECTORIES = {
    ".github", "dist", "docs", "examples", "references", "scripts", "tests", "wordpress-plugin",
}
EXCLUDED_NAMES = {"__pycache__", ".runtime", "credentials.json", ".env"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log"}
FIXED_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def version():
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise SystemExit(f"VERSION must contain X.Y.Z, found: {value!r}")
    return value


def included_files():
    files = [ROOT / name for name in sorted(TOP_LEVEL_FILES)]
    for directory in sorted(TOP_LEVEL_DIRECTORIES):
        base = ROOT / directory
        files.extend(path for path in base.rglob("*") if path.is_file())
    result = []
    for path in files:
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_NAMES for part in relative.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        result.append(path)
    return sorted(set(result), key=lambda item: item.relative_to(ROOT).as_posix())


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_deterministic_zip(destination):
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in included_files():
            relative = source.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{PACKAGE_ROOT}/{relative}", FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())


def build(output_directory=RELEASE_DIR):
    release = Path(output_directory)
    release.mkdir(parents=True, exist_ok=True)
    for existing in release.iterdir():
        if existing.is_file():
            existing.unlink()

    current = version()
    if not PLUGIN_SOURCE.is_file():
        raise SystemExit("Build the WordPress bridge ZIP before building the release.")

    package = release / f"wp-draft-publisher-v{current}.zip"
    plugin = release / PLUGIN_SOURCE.name
    write_deterministic_zip(package)
    shutil.copy2(PLUGIN_SOURCE, plugin)

    artifacts = [package, plugin]
    checksums = {artifact.name: sha256(artifact) for artifact in artifacts}
    checksum_file = release / "SHA256SUMS.txt"
    with checksum_file.open("w", encoding="utf-8", newline="\n") as target:
        target.write("".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items())))
    manifest = release / "release-manifest.json"
    with manifest.open("w", encoding="utf-8", newline="\n") as target:
        target.write(json.dumps({"project": "wp-draft-publisher", "version": current, "artifacts": checksums}, indent=2) + "\n")
    return {"version": current, "directory": str(release), "artifacts": checksums}


def main():
    parser = argparse.ArgumentParser(description="Build deterministic WP Draft Publisher release artifacts.")
    parser.add_argument("output_directory", nargs="?", default=str(RELEASE_DIR))
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.output_directory), ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
