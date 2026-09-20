# Integration gateway operations

The optional gateway is disabled by default. Install the `gateway` extra before serving the FastAPI adapter. Run `local-ai-gateway config-check` to inspect non-secret configuration and `local-ai-gateway auth-token-check` to verify a token digest without printing a token.

`local-ai-gateway mcp-stdio` starts the local MCP server boundary. MCP server support is stdio-only; Friday does not implement an MCP client. Stdio has no remote bearer authentication: the launching local process/user is trusted, while every operation still passes through the typed gateway service and configured repository/scope policy. Diagnostics go to stderr and stdout is reserved for JSON-RPC.

Keep the listener on loopback unless a deliberate deployment adds TLS, firewalling, stronger authentication, and signed webhook ingress. GitHub mappings must be explicit; unknown repositories fail closed. Normal tests use `FakeGitHubTransport` and never require public internet. External outages affect publication state only and cannot trigger an unbounded retry or execution loop.

For review-gated GitHub publication, register the managed repository with
`local-ai-repo scan REPOSITORY_ID PATH --publication-mapping OWNER/REPOSITORY`.
Set `LOCAL_AI_GITHUB_ENABLED=true`, keep `LOCAL_AI_GITHUB_TOKEN` only in the
protected local environment, and include `github_write` in
`LOCAL_AI_GATEWAY_SCOPES`. The presentation publication route still requires the
configured bearer token; neither Astra nor the Learner Twin stores it. Candidate
approval and publication remain separate requests, and only a succeeded
`friday/task/` task with a final commit and matching local/remote repository
identity can reach the existing publisher.
