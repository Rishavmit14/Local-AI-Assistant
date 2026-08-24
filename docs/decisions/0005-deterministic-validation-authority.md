# ADR 0005: Deterministic validation remains authoritative

- Status: accepted
- Date: 2026-08-24

## Decision

Repository configuration and deterministic code facts select validation, review, and security checks. Qwen may generate scoped tests or repair patches and provide an advisory review, but it cannot mark a skipped required check successful, remove a deterministic finding, downgrade policy, or expand scope.

Validation runs targeted-first and full-final according to risk. All mutation continues through Stage 4 plan binding and scope enforcement. A scope or risk increase requires a new validated plan and renewed approval when applicable.

## Consequences

This provides auditable failure provenance and preserves local/offline operation. Heuristic scanners can produce warnings and do not replace dedicated audits. Missing required local tools block completion rather than producing false confidence.
