# Security Policy

## Reporting

Do not open a public issue for a suspected vulnerability or exposed secret. Contact the repository owner privately with affected versions, reproduction steps, impact, and a proposed mitigation if known.

## Local-first boundary

The application binds model and UI services to `127.0.0.1` by default. Exposing either service to another interface requires authentication, transport security, network filtering, and an explicit threat review.

Never commit credentials, private keys, tokens, `.env` files, model binaries, private documents, embeddings, vector indexes, logs, or runtime databases. Uploaded documents and derived indexes are private runtime state and belong outside Git.

## Coding-agent boundary

Model output is untrusted input. A proposed mutation must remain within an isolated Git transaction and pass patch preflight, scope checks, structural/static validation, relevant tests, bounded repair, and review. Destructive shell commands, privilege escalation, credential operations, force pushes, and production/security-sensitive changes require explicit approval.

The bundled demo authentication app is an intentionally small test fixture. Its SHA-256 password hashing and hard-coded demo key are not suitable for production.
