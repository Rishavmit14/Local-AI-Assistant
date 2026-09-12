# ADR 0022: Roles are sequential prompt contexts over one local model

## Status

Accepted

## Decision

Friday uses a local `RoleOrchestrator` with typed role clients over the already
configured Qwen model. Invocations are serialized and role instructions are
additive to caller-supplied system context. Roles have no capabilities beyond
making a local model request; they cannot execute tools, approve tasks, mutate
state, access credentials, or select another model.

## Consequences

Friday retains one coherent user-facing identity while its existing subsystems
can use specialized prompts. This introduces no multi-agent runtime, cloud
dependency, parallel inference, or authority bypass. Model replacement/addition
remains governed by ADR 0014.
