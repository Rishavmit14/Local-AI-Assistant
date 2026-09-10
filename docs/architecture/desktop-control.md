# Friday desktop control

## Stage 16 foundation

`DesktopControlService` is independent from perception and repository execution.
It defaults to an empty `LOCAL_AI_DESKTOP_ALLOWED_APPS` allowlist. A caller can
only propose `focus_app` or `launch_app` for an exact valid configured app ID.

Every proposal is recorded in local SQLite with a bounded approval window. A
separate explicit approval transition is required before a one-time execution.
Focus uses the fixed GNOME `FocusApp` D-Bus method; launch uses the fixed `gio
launch` argument vector. No endpoint accepts a shell command, script, path,
keyboard/mouse coordinate, browser URL, or caller-supplied D-Bus expression.

An explicit `open_uri` action is the narrow browser boundary. It accepts only an
HTTPS URI whose exact origin appears in the empty-by-default
`LOCAL_AI_DESKTOP_ALLOWED_ORIGINS` list, then uses a fixed `gio open` vector
only after approval. It is URI dispatch, not browser automation: no page read,
form fill, download, cookie, credential, or DevTools authority is granted.

The Friday cinematic UI is a projection of this same local action audit. It
shows a pending action and offers a deliberate approval action. It cannot create
an action, expand the allowlist, or bypass the lifecycle.
