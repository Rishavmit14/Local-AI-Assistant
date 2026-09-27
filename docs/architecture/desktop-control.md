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

An explicit `open_file` action accepts only an existing regular file beneath an
exact root in the empty-by-default `LOCAL_AI_DESKTOP_ALLOWED_FILE_ROOTS` list.
It resolves the path before audit and approval, then uses fixed `gio open`
arguments. It cannot enumerate, read through the API, create, overwrite, move,
rename, or delete files.

The semantic UI boundary accepts only exact `application::control::action`
entries in the empty-by-default `LOCAL_AI_DESKTOP_ALLOWED_ACCESSIBILITY_TARGETS`
list. A bounded local AT-SPI traversal may invoke only that named accessibility
action after approval. It never accepts a selector, coordinate, key sequence, or
screen-derived target and emits no accessibility-tree text through Friday.

The Friday cinematic UI and Astra Attention are projections of this same local
action audit. Astra loads canonical actions, treats review as read-only, and
calls the existing per-action approval and execution routes separately. It
re-fetches the ledger after each transition, exposes no decline/retry lifecycle,
and does not create proposals from free-form targets. The exact target is shown
only for bounded application IDs suitable for informed approval; History keeps
its separate target-redaction policy. Task-plan approval remains behind its
authenticated Gateway boundary and is not the same authority as desktop action
approval.

`launch_app` persists the exact allowlisted app ID for review and audit. At
execution, `DesktopControlService` resolves its exact desktop-file basename in
configured system XDG `applications` directories because `gio launch` accepts
a desktop-file path. It does not search `XDG_DATA_HOME` or recurse through the
owner's files. Missing, duplicate, path-like, symlink-alias, or otherwise
ambiguous resolution fails closed. The subprocess receives a fixed argument
vector without a shell; `open_uri`, `open_file`, and accessibility handling
retain their existing semantics.

Isolated Astra qualification physically exercised only
`launch_app -> org.gnome.Calculator.desktop`, including separate owner approval
and execution and reconstruction in Attention and History. That proves no
other desktop action class. The stale qualification record remains `expired`
and the first physically attempted record remains `failed`; neither is reset
or retried.
