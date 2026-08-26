# Stage 10 repository onboarding

Friday only scans repositories that an authorized operator explicitly registers
through `RepositoryOnboardingService`.  The service resolves the canonical Git
root, enforces configured allowed roots, rejects Friday runtime/worktree roots,
and records a stable fingerprint made from the canonical path, Git common
directory, and root commits. Credential-free remote identities are retained as
metadata but do not alter stable repository identity. HEAD and scan inputs form
a separate mutable revision. Every scan detects an identity swap.

Readiness is static and bounded.  It reads manifests, source extensions,
instructions, CI metadata, ignore/attribute files, and worktree metadata.  It
does not install dependencies, invoke package scripts, run CI commands, build,
or execute repository code.  Tool versions are collected only with fixed
`--version` probes.  Generated/vendor directories, symlinks, binaries, and
secret-like files are bounded or represented by metadata; secret contents are
never included in a report.

Reports distinguish clean/dirty/conflicted repositories, supported languages,
components, candidate validation commands, missing tools, indexing state,
warnings, and typed blockers.  A conflicted checkout or unsafe package script
is blocked.  A dirty checkout is never cleaned or modified.  Readiness is an
additional gate before the existing Stage 3 approval and Stage 8 isolated
execution path; it does not grant mutation authority.

Autonomous mutation fails closed when a profile is missing or corrupt. The
gateway adapter and `local-ai-code-agent` perform fresh identity/readiness
verification, and the latter verifies repository-scoped Stage 2 index evidence
again immediately before Stage 8 mutation. Registry schema 2 is atomic JSON;
malformed or unsupported registries require explicit re-onboarding.

The read-only module CLI can be run with `python -m
local_ai_assistant.onboarding_cli list|inspect|scan|readiness|dry-run`.  Its
normal runtime registry is `LOCAL_AI_ONBOARDING_REGISTRY`; allowed roots are
configured with `LOCAL_AI_ONBOARDING_ALLOWED_ROOTS` (path-separated), defaulting
to Friday's managed repository root.  No onboarding operation publishes or
changes Git remotes.

Threat model coverage includes path traversal and symlink escapes, repository
identity swaps, hostile instructions, package/CI command injection, generated
tree explosions, secret files, dirty/conflicted worktrees, submodules/LFS, and
oversized repositories.  Project setup and heavy indexing remain explicit
operator actions under the existing isolation and validation policy.
