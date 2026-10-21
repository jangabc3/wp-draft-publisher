# Uninstall and revoke access

Remove the Codex skill while keeping encrypted settings:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\uninstall.ps1
```

Remove the skill, encrypted credentials, and editorial profile:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\uninstall.ps1 -RemoveCredentials
```

Then open the dedicated user's WordPress profile and revoke the `WP Draft Publisher` Application Password. Removing local files does not revoke a server-side Application Password.

To remove one named site while keeping the others, run `scripts\remove-site.ps1 -Site "site-key"`. It asks for confirmation and deletes only that site's local configuration. Revoke that site's Application Password separately in WordPress.

Remove the `wp-draft-publisher` entry from Claude Desktop, Cursor, or another MCP client and restart that application. If recovery snapshots and activity history are no longer needed, deactivate and delete Draft Publisher REST Bridge in WordPress.
