# Friday frontend boundary

The browser is a presentation client. Friday's API remains authoritative for
conversation, Career Forge, Projects, task history, authentication, CSRF, and
all durable state. UI availability or local preview data never implies that a
backend capability or owner action succeeded.

## Local production origin

The built frontend is served at `http://127.0.0.1:5193` by the user-level
`friday-ui.service`. The service reads static files from the accepted main
worktree's `frontend/dist`, binds only to IPv4 loopback, serves only GET/HEAD
static requests, and uses a same-origin proxy for `/api` and `/health` to the
configured loopback Friday API. It rejects non-loopback clients, unexpected
Host headers, traversal, and write methods to static paths. It adds no API
routes and stores no state.

Incoming API authorization, cookies, and CSRF headers pass through unchanged;
client-supplied `x-friday-local-owner` and forwarded-address headers are
removed. The server reuses the existing local Owner bridge. That bridge can add
the private capability only to the exact `POST
/api/v1/project-execution/restore` request when the connection, Origin, and
Host match the configured loopback UI origin. The API remains responsible for
bearer authentication, CSRF validation, owner-task authorization, and action
policy. The bridge reads the capability file on each eligible request and
fails closed if it is missing, revoked, or invalid.

The service runs without root, uses no new package, and is supervised by the
user systemd manager. `frontend/systemd/friday-ui-rollback.service` preserves a
manual rollback path to the prior GCA checkout on the same origin; it is
disabled during normal operation. Neither service restarts Friday's API, Qwen,
voice, or computer-control services. Installation, checks, and rollback are
documented in `docs/operations/friday-ui.md` and ADR 0051.
