# Integration gateway operations

The optional gateway is disabled by default. Install the `gateway` extra before serving the FastAPI adapter. Run `local-ai-gateway config-check` to inspect non-secret configuration and `local-ai-gateway auth-token-check` to verify a token digest without printing a token.

Keep the listener on loopback unless a deliberate deployment adds TLS, firewalling, stronger authentication, and signed webhook ingress. GitHub mappings must be explicit; unknown repositories fail closed. Normal tests use `FakeGitHubTransport` and never require public internet. External outages affect publication state only and cannot trigger an unbounded retry or execution loop.
