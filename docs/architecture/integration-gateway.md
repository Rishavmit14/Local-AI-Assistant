# Native integration gateway

Stage 9 adds a thin, local-first boundary around Friday's existing services:

`external request → authenticated gateway → task history/planner → Stage 8 isolation → validation/review`

The gateway never accepts a filesystem path, shell command, environment, worktree, or sandbox override. Repository IDs are explicit mappings. The default bind is `127.0.0.1`; privileged routes require a bearer token whose SHA-256 digest is configured through `LOCAL_AI_GATEWAY_TOKEN_HASH` (the plaintext token is never persisted).

Friday exposes an MCP server over local stdio only (no MCP client). Stdio inherits the authority of its launching local user; it is not a remotely authenticated transport and must not be exposed as a network service.

Typed gateway services and adapters do not duplicate planning, approval, execution, or Git transaction logic. GitHub issue text is untrusted task data and cannot override system, owner, or repository instructions. The event bus is bounded and Stage 7 history remains the durable audit source.
