# Integration gateway operations

## Browser Project approval and execution

Configure `LOCAL_AI_PROJECT_OWNER_TOKEN_HASH` as the SHA-256 hex digest of a
strong, separate owner unlock token and
`LOCAL_AI_PROJECT_EXECUTION_ALLOWED_ORIGINS` as comma-separated exact loopback
browser origins. Configure `LOCAL_AI_GATEWAY_SCOPES` with both
`submit_approval` and `request_execution`; the Presentation API fails closed
when owner authentication, origins, or required server-side scopes are absent.
The Gateway bearer credential remains server-side and is never sent to or
stored by the browser. The browser receives only a short-lived HttpOnly,
strict-SameSite session cookie and in-memory CSRF token. Removing the owner
digest/origins or required scopes disables new authorizations; restart the
Presentation API to revoke already-issued volatile sessions. Approval binds
the current Objective/task and plan hash; execution checks that binding again
before the isolated Gateway dispatcher admits work.

The optional gateway is disabled by default. Install the `gateway` extra before serving the FastAPI adapter. Run `local-ai-gateway config-check` to inspect non-secret configuration and `local-ai-gateway auth-token-check` to verify a token digest without printing a token.

`local-ai-gateway mcp-stdio` starts the local MCP server boundary. MCP server support is stdio-only; Friday does not implement an MCP client. Stdio has no remote bearer authentication: the launching local process/user is trusted, while every operation still passes through the typed gateway service and configured repository/scope policy. Diagnostics go to stderr and stdout is reserved for JSON-RPC.

Keep the listener on loopback unless a deliberate deployment adds TLS, firewalling, stronger authentication, and signed webhook ingress. GitHub mappings must be explicit; unknown repositories fail closed. Normal tests use `FakeGitHubTransport` and never require public internet. External outages affect publication state only and cannot trigger an unbounded retry or execution loop.

For review-gated GitHub publication, register the managed repository with
`local-ai-repo scan REPOSITORY_ID PATH --publication-mapping OWNER/REPOSITORY`.
Set `LOCAL_AI_GITHUB_ENABLED=true`, register one explicit publication mapping,
and include `github_write` in `LOCAL_AI_GATEWAY_SCOPES`. Prefer the
server-side `gh-keyring:github.com:ACCOUNT` credential reference with an exact
`LOCAL_AI_GITHUB_ALLOWED_REPOSITORY` and purpose
`learner_project_public_proof`. Friday resolves the GitHub CLI credential from
the owner OS keyring and checks account identity during startup. The legacy
`LOCAL_AI_GITHUB_TOKEN` remains available for protected service environments;
never put it in browser-visible configuration or logs. Neither Astra nor the
Learner Twin stores it. Candidate approval and publication remain separate
requests, and only a succeeded
`friday/task/` task with a final commit and matching local/remote repository
identity can reach the existing publisher.

Owner-reviewed task checkpoint restore is disabled unless all of these
protected local environment values are configured:

- `LOCAL_AI_ROLLBACK_OWNER_TOKEN_HASH`: SHA-256 hex digest of a strong local
  owner unlock token.
- `LOCAL_AI_ROLLBACK_GATEWAY_TOKEN`: server-only plaintext bridge credential.
- `LOCAL_AI_ROLLBACK_GATEWAY_TOKEN_HASH`: its SHA-256 hex digest.
- `LOCAL_AI_ROLLBACK_ALLOWED_ORIGINS`: comma-separated exact Astra origins.

The bridge is constructed with only `request_rollback`; do not reuse the
execution token. Keep both plaintext values out of repository, frontend build,
logs, and browser storage. The owner token is entered only at unlock. Astra gets
an HttpOnly, strict-SameSite, 10-minute session cookie and an in-memory CSRF
token; restart revokes sessions. Remove the protected owner digest and bridge
values to revoke this capability, then reload the local Presentation API.
Rollback is limited to eligible schema-2 checkpoints in non-protected isolated
task worktrees. This flow does not undo publication, canonical-repository
changes, desktop actions, or arbitrary files. Candidate qualification should
use disposable task state only.
