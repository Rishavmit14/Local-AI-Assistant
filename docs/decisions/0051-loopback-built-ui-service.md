# ADR 0051: Serve the built Friday UI through a loopback user service

- **Status:** Accepted for Stage 28 UI publication
- **Date:** 2026-10-14

## Context

Friday's established browser origin is `127.0.0.1:5193`. It was served by an
unsupervised Vite development server, so the approved UI was not the persistent
default and would not reliably return after a laptop restart. The browser must
continue to use the existing Friday API, authentication, CSRF, and local Owner
restore boundaries.

## Decision

Serve the production build with a small Node.js server using only Node's
built-in HTTP and filesystem modules. Run it as an enabled user-level systemd
service, bind only to `127.0.0.1:5193`, serve immutable build output without
write access, and proxy only `/api` and `/health` to the configured loopback
API. Reuse `localOwnerBridge` for the exact pre-existing local restore path;
strip client-supplied owner-capability and forwarded-address headers before
proxying. Keep the previous GCA Vite checkout in a separate disabled rollback
unit. No backend or model process is restarted by UI publication.

## Consequences

- Main's built frontend is the normal UI and is supervised across the user
  session lifecycle.
- The frontend server has no database, model, planning, task, or owner-policy
  authority. The backend still makes those decisions.
- The API receives browser requests on the established same origin, retaining
  existing cookies, bearer headers, and CSRF behavior.
- A private per-user EnvironmentFile supplies only paths and loopback origins;
  the Owner capability itself remains in Friday's separately protected file.
- The unit sets `NoNewPrivileges=yes` and a restrictive umask. This host's user
  systemd manager rejects namespace and capability sandbox setup, so those
  unsupported directives are omitted. The service remains an owner-run,
  loopback-only UI process; API authentication and Owner-task authorization are
  still enforced by the backend.
- `systemctl --user disable --now friday-ui.service` followed by enabling the
  rollback unit restores the previous UI without changing Friday's API or
  Qwen. The reverse steps restore the accepted UI.

## Rejected option

Do not run `vite preview` as the persistent frontend service. Vite documents it
as a local build-preview server, not a production server. The Node service is
small, dependency-free, testable, and limited to Friday's local static/API
boundary.
