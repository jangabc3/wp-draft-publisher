import os
import base64
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SiteProfileTests(unittest.TestCase):
    @staticmethod
    def run_windows_powershell(command):
        encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
        )

    def test_runtime_and_setup_use_scoped_site_directories(self):
        config = (ROOT / "scripts" / "site-config.ps1").read_text(encoding="utf-8")
        run = (ROOT / "scripts" / "run.ps1").read_text(encoding="utf-8")
        setup = (ROOT / "scripts" / "setup-credentials.ps1").read_text(encoding="utf-8")
        self.assertIn("Assert-WpdpConfigDirectory", config)
        self.assertIn("sites.json", config)
        self.assertIn("--site", run)
        self.assertIn("selectedSite.directory", run)
        self.assertIn("Register-WpdpSite", setup)
        self.assertIn("ProtectedData]::Protect", setup)

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell path behavior")
    def test_registry_selects_default_and_named_sites(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            script = ROOT / "scripts" / "site-config.ps1"
            command = (
                f"$env:LOCALAPPDATA='{directory}'; . '{script}'; "
                "$null=Register-WpdpSite 'personal' 'Personal' 'https://one.example' -SetDefault; "
                "$null=Register-WpdpSite 'company' 'Company' 'https://two.example'; "
                "$a=Resolve-WpdpSite ''; $b=Resolve-WpdpSite 'company'; "
                "if($a.key -ne 'personal' -or $b.key -ne 'company'){exit 9}"
            )
            # Windows PowerShell decodes -Command using the active legacy code page,
            # which corrupts a Unicode workspace path. -EncodedCommand is UTF-16LE.
            completed = self.run_windows_powershell(command)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell path behavior")
    def test_remove_site_is_scoped_and_reassigns_default(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            config = ROOT / "scripts" / "site-config.ps1"
            remove = ROOT / "scripts" / "remove-site.ps1"
            command = (
                f"$env:LOCALAPPDATA='{directory}'; . '{config}'; "
                "$one=Register-WpdpSite 'personal' 'Personal' 'https://one.example' -SetDefault; "
                "$two=Register-WpdpSite 'company' 'Company' 'https://two.example'; "
                "New-Item -ItemType Directory -Force $one,$two|Out-Null; "
                "Set-Content -LiteralPath (Join-Path $one 'credentials.json') -Value '{}'; "
                f"& '{remove}' -Site personal -Confirm:$false; "
                "$r=Read-WpdpRegistry; "
                "if($r.default_site -ne 'company' -or @($r.sites).Count -ne 1 -or (Test-Path -LiteralPath $one) -or -not (Test-Path -LiteralPath $two)){exit 9}"
            )
            completed = self.run_windows_powershell(command)
            self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
