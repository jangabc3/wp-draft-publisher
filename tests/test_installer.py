from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_installer_checks_python_and_safety_tests(self):
        text = (ROOT / "install.ps1").read_text(encoding="utf-8")
        self.assertIn("Python 3.9 or later", text)
        self.assertIn("unittest discover", text)
        self.assertIn("scripts\\setup-credentials.ps1", text)
        self.assertIn("doctor", text)

    def test_installer_uses_staging_and_backup(self):
        text = (ROOT / "install.ps1").read_text(encoding="utf-8")
        self.assertIn("$staging", text)
        self.assertIn("$backup", text)
        self.assertIn("Move-Item -LiteralPath", text)

    def test_uninstaller_is_scoped_to_codex_skills(self):
        text = (ROOT / "uninstall.ps1").read_text(encoding="utf-8")
        self.assertIn(".codex\\skills", text)
        self.assertIn("StartsWith", text)
        self.assertIn("SupportsShouldProcess", text)


if __name__ == "__main__":
    unittest.main()

