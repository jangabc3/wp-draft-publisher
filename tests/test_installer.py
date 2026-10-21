from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_installer_checks_python_and_safety_tests(self):
        text = (ROOT / "install.ps1").read_text(encoding="utf-8")
        self.assertIn("Python 3.9 or later", text)
        self.assertIn("sep=chr(46)", text)
        self.assertIn("unittest discover", text)
        self.assertIn("scripts\\setup-credentials.ps1", text)
        self.assertIn("scripts\\setup-profile.ps1", text)
        self.assertIn("doctor", text)

    def test_installer_uses_staging_and_backup(self):
        text = (ROOT / "install.ps1").read_text(encoding="utf-8")
        self.assertIn("$staging", text)
        self.assertIn("$backup", text)
        self.assertIn("Move-Item -LiteralPath", text)
        self.assertIn("'integration'", text)
        self.assertIn("'tests'", text)

    def test_uninstaller_is_scoped_to_codex_skills(self):
        text = (ROOT / "uninstall.ps1").read_text(encoding="utf-8")
        self.assertIn(".codex\\skills", text)
        self.assertIn("StartsWith", text)
        self.assertIn("SupportsShouldProcess", text)
        self.assertIn("$skillsPrefix", text)
        self.assertIn("$localDataPrefix", text)

    def test_profile_scripts_keep_preferences_outside_the_skill(self):
        setup = (ROOT / "scripts" / "setup-profile.ps1").read_text(encoding="utf-8")
        show = (ROOT / "scripts" / "show-profile.ps1").read_text(encoding="utf-8")
        self.assertIn("LOCALAPPDATA", setup)
        self.assertIn("editorial-profile.json", setup)
        self.assertNotIn("encrypted_password", setup)
        self.assertIn("editorial_profile_missing", show)
        self.assertIn("minimum_related_links", show)
        self.assertIn("connection.json", setup)
        self.assertIn("schema_version = 2", setup)
        self.assertIn("site_topic", setup)
        self.assertIn("default_category", setup)
        self.assertIn("writing_brief", show)

    def test_connection_wizard_verifies_before_saving_and_keeps_metadata_separate(self):
        setup = (ROOT / "scripts" / "setup-credentials.ps1").read_text(encoding="utf-8")
        self.assertIn("Connecting without saving the password", setup)
        self.assertIn("wordpress.py') doctor", setup)
        self.assertIn("No credentials were saved", setup)
        self.assertIn("connection.json", setup)
        self.assertIn("ProtectedData]::Protect", setup)
        self.assertLess(setup.index("wordpress.py') doctor"), setup.index("credentials.json"))

    def test_baseline_command_covers_parse_compile_tests_build_and_public_scan(self):
        baseline = (ROOT / "scripts" / "check-baseline.ps1").read_text(encoding="utf-8")
        for expected in ("ParseFile", "compileall", "build_plugin.py", "unittest discover", "check_repository.py", "check_public_release.py"):
            self.assertIn(expected, baseline)

    def test_command_help_is_available_before_credentials_exist(self):
        runner = (ROOT / "scripts" / "run.ps1").read_text(encoding="utf-8")
        self.assertIn("Help must remain available before first-time configuration", runner)
        self.assertLess(runner.index("@('--help', '-h')"), runner.index("Resolve-WpdpSite $siteName"))

    def test_integration_readiness_probe_is_cross_platform(self):
        integration = (ROOT / "scripts" / "run-integration.ps1").read_text(encoding="utf-8")
        self.assertIn("Get-Command curl.exe", integration)
        self.assertIn("Get-Command curl -CommandType Application", integration)
        self.assertIn("& $curlPath", integration)
        self.assertNotIn("& curl.exe", integration)


if __name__ == "__main__":
    unittest.main()

