# Contributing

Thank you for helping improve WP Draft Publisher.

## Before opening a change

Search existing issues first. Use a bug report for reproducible defects and a feature request for proposed behavior. Keep each pull request focused on one problem.

## Development setup

Requirements:

- Python 3.9 or later
- PowerShell 5.1 or later
- Docker Desktop for live WordPress tests

Run the fast test suite:

```powershell
python -m unittest discover -s tests -v
```

Run the disposable live WordPress suite:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-integration.ps1
```

Build the release files:

```powershell
python .\scripts\build_release.py
```

## Pull requests

- Add or update tests for behavior changes.
- Preserve the draft-only boundary and do not add automatic publishing.
- Keep secrets, site URLs, prompts, and article bodies out of logs and fixtures.
- Update `CHANGELOG.md` for user-visible changes.
- Run `python -m unittest discover -s tests -v` before submitting.
- Explain the problem, resulting behavior, validation, and material risks in the pull request description.

By contributing, you agree that your contribution is licensed under the MIT License. The WordPress bridge plugin remains GPL-2.0-or-later as declared in its source.
