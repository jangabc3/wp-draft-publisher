# Security policy

## Supported versions

Security fixes are provided for the latest released version.

| Version | Supported |
| --- | --- |
| 1.0.x | Yes |
| Earlier versions | No |

## Reporting a vulnerability

Use **Security → Report a vulnerability** in the GitHub repository to submit a private report. Include the affected version, reproduction steps, impact, and any suggested mitigation. Do not include real WordPress credentials, article contents, or private site URLs.

If private vulnerability reporting is unavailable, contact the repository owner privately before opening an issue. Do not publish exploitable details in a public issue.

You should receive an acknowledgement within seven days. Confirmed issues will be prioritized by impact and released with an appropriate advisory and patched version.

## Credential handling

- Use a dedicated WordPress user with the Editor role or the smallest permissions that meet your workflow.
- Use a WordPress Application Password rather than the account password.
- Revoke the Application Password immediately if a device or encrypted credential file is compromised.
- Never attach `%LOCALAPPDATA%\WPDraftPublisher\credentials.json` to an issue.
