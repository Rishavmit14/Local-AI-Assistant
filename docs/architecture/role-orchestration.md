# Role orchestration

Stage 19 keeps one user-facing Friday and one local general-purpose Qwen model.
`RoleOrchestrator` supplies bounded prompt-only clients for conversation,
reasoning, coding, vision, retrieval, planning, coder, reviewer, debugger,
tester, and security roles. A role is context, not an identity, process, tool,
or privilege boundary.

One invocation lock serializes all role calls over the shared local model. The
orchestrator records only bounded role/timing/success metadata in memory; it does
not persist prompts or responses, create agents, call a network service, or own a
task lifecycle. It does not accept a model identifier, so adding another general
model requires the separate ADR 0014 evidence process.

Conversation and native planning use their matching role clients. The code-agent
uses planner, coder, debugger, tester, and reviewer clients at its existing
model invocation sites. This changes neither exact-plan approval, tool scope,
validation, isolation, Git, task history, nor deterministic security review.
