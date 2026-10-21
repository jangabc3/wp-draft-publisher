# Verified baseline

Run this check before and after each public-facing feature change:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-baseline.ps1
```

The command parses the PowerShell entry points, compiles Python sources, rebuilds the deterministic bridge ZIP, runs the unit and source-contract suite, and scans public files for common credential or private-site material.

## Protected behavior

Changes must preserve these guarantees:

- only drafts can be created or updated;
- a stable slug prevents duplicate draft creation;
- stale updates stop before overwriting a newer edit;
- bridge-guarded updates create private recovery snapshots;
- saved post, taxonomy, featured image, and SEO values are read back and verified;
- reused media is never removed during rollback;
- mutating requests are not retried blindly;
- credentials, prompt text, and article bodies are not written to activity records;
- the public package contains no personal site configuration or credentials.

## First-use acceptance check

A clean Windows user should be able to:

1. run `install.cmd` without administrator rights;
2. enter an HTTPS WordPress address, username, and Application Password;
3. receive an actionable message when authentication, REST access, media, taxonomy, or the bridge is unavailable;
4. see the detected site language, categories, SEO provider, bridge version, and account permissions;
5. finish the editorial profile and read-only capability check;
6. create one verified draft without changing a published post.

The WordPress administrator should be able to open **Tools → Draft Publisher** to review server readiness, setup guidance, recent privacy-safe activity, and permitted recovery snapshots.
