import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_release.py"
SPEC = importlib.util.spec_from_file_location("wpdp_release", MODULE_PATH)
release_builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_builder)


class ReleaseTests(unittest.TestCase):
    def test_release_metadata_and_community_files_exist(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "1.0.0")
        for filename in (
            "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", "SUPPORT.md",
            "README.ko.md", ".github/workflows/release.yml",
            ".github/ISSUE_TEMPLATE/bug.yml", ".github/ISSUE_TEMPLATE/feature.yml",
            "docs/RELEASE_NOTES_v1.0.0.md",
            "scripts/test-release-package.ps1", "scripts/check-release-candidate.ps1",
        ):
            self.assertTrue((ROOT / filename).is_file(), filename)

    def test_release_builder_creates_installable_zip_and_matching_checksums(self):
        with tempfile.TemporaryDirectory(prefix=".wpdp-release-test-", dir=ROOT) as temporary:
            output = Path(temporary)
            result = release_builder.build(output)
            package = output / "wp-draft-publisher-v1.0.0.zip"
            with zipfile.ZipFile(package) as archive:
                names = archive.namelist()
                self.assertIn("wp-draft-publisher/install.cmd", names)
                self.assertIn("wp-draft-publisher/SKILL.md", names)
                self.assertIn("wp-draft-publisher/README.ko.md", names)
                self.assertTrue(all("credentials.json" not in name for name in names))
                self.assertTrue(all("__pycache__" not in name for name in names))

            checksums = {}
            for line in (output / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
                digest, filename = line.split("  ", 1)
                checksums[filename] = digest
            for filename, expected in checksums.items():
                actual = hashlib.sha256((output / filename).read_bytes()).hexdigest()
                self.assertEqual(actual, expected)
            manifest = json.loads((output / "release-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], result["version"])
            self.assertEqual(manifest["artifacts"], checksums)

    def test_release_workflow_gates_publish_on_clean_windows_package(self):
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("package-windows:", workflow)
        self.assertIn("./scripts/test-release-package.ps1", workflow)
        self.assertIn("needs: [validate, integration, package-windows]", workflow)

    def test_release_builder_cli_accepts_an_isolated_output_directory(self):
        with tempfile.TemporaryDirectory(prefix=".wpdp-release-cli-", dir=ROOT) as temporary:
            result = subprocess.run(
                [sys.executable, str(MODULE_PATH), temporary],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(temporary) / "SHA256SUMS.txt").is_file())


if __name__ == "__main__":
    unittest.main()
