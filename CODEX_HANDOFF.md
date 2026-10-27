# Friday handoff — Stage 33 design-ready; implementation not started

Updated 2026-10-27. The Owner designated Stage 33 as Telegram Remote Owner Control and moved the earlier screen-aware Career Forge/DLP recommendation provisionally to Stage 34. This checkpoint registers the architecture and roadmap only. Stage 33 is PROPOSED / DESIGN-READY, not ACCEPTED or DEPLOYED. There is no Telegram code, bot token, phone signer, service unit, migration, or production change.

## Repository and publication state

- Documentation worktree: /AI/projects/friday-stage33-telegram
- Branch: stage-33/telegram-remote-owner-control
- Base checkpoint: 899214e023f3ac97452db8ea625e9805961d14c5, verified as origin/main before creating this worktree.
- The separate original checkout /AI/projects/Local-AI-Assistant-terra-integration remains on recovery/local-main-before-stage28 at 47ae92bba1c3b50d9dd6f2264d95b6cfaf275e75 with pre-existing dirty CODEX_HANDOFF.md and ROADMAP.md. Those changes were preserved and not incorporated.
- Protected production source checkout /AI/projects/Local-AI-Assistant remains on stage-22/product-integration with owner-owned Pocket/Anna changes. Do not modify it.
- Stage 32 source deployed to production: 512d1d521b44b853d7ffebd62222e087b199c3a3. Exact release evidence and rollback constraints are in docs/operations/stage32-release-plan.md.
- Stage 33 publication recovery is the clean committed HEAD of this worktree, the stage-33 branch, and main after the normal fast-forward publication. Resolve its exact object with Git; the final report records the SHA. No force-push or deployment is authorized or required by this design task.

## Runtime and protected state observed

At initial design review, friday-local-ai.service, friday-ui.service, llama-qwen.service, and local-ai-ui.service were active. The API current pointer resolved to the immutable Stage 32 source release above. The production API/UI and Qwen services were not restarted by this documentation work. No Telegram request, microphone/speech test, screen capture, learner mutation, computer action, privileged operation, credential operation, database write, or production deployment was performed.

The Stage 32 release report records 15 integrity-checked stores and historical computer-agency actions, including 12 in_doubt and three result_present actions. This task did not inspect or mutate those records; do not replay them. Preserve current production data and the immutable Stage 32 release during future Stage 33 candidate work.

## Stage 33 design

- Primary design: docs/architecture/telegram-remote-owner.md.
- Operations and future implementation runbook: docs/operations/telegram-remote-owner.md.
- Proposed ADR: docs/decisions/0057-telegram-remote-owner-control.md.
- Acceptance plan: 14 real Owner-phone-to-laptop scenarios with authority, effects, evidence, negative controls, recovery and PASS criteria.
- Core transport: one private Owner-paired bot, outbound long polling, no public Friday API, durable deduplicated ingress/outbox, exact numeric Owner ID and private-chat binding.
- Canonical routing: Friday Conversation/Qwen, existing voice, Memory/Career Forge, Perception, Computer Agency, Objectives/TaskHistory/Gateway, publication, cancellation and proactive-notification authorities.
- Consequential work: cryptographic phone signature over the exact canonical action and operation digest. The bot token does not grant root access. Production Friday is not yet trusted by the Owner Sovereign broker; production identity integration and qualification are a Stage 33 prerequisite.
- Recorded voice notes are supported by design; native Telegram real-time phone calls are unsupported. A Telegram Mini App is optional.
- The host did not have FFmpeg on PATH during review; select and pin a local bounded audio encoder before voice acceptance.

## Product allocation

- Stage 33: PROPOSED / DESIGN-READY only. Product matrix row 62 is ABSENT until implementation and end-to-end Owner qualification.
- Stage 34: PROVISIONAL Career Forge advanced owner integration, including the previously recommended retained-screen tutoring journey and the full retained Stage 22 / matrix row 60 and 61 requirements.
- Rows 60 and 61 remain PARTIAL with unchanged identities. Earlier accepted work and requirements are preserved.

## Validation and current environment limits

- All local links in the ten changed documentation files resolve; targeted Telegram-token, private-key, GitHub-token and AWS-key scans are clear; `git diff --check` is clean. `gitleaks` is not installed in this environment.
- The canonical repository verifier compiled the source successfully. Its regression reported 2,025 passed, 6 skipped and 14 failed. Twelve deterministic execution-qualification cases could not complete their candidate validation loops because sandbox commands failed; the captured diagnostics include `/AI/projects/local-ai/.venv/bin/python: No such file or directory`. `test_desktop_runtime_identity` also reports a distribution-source mismatch in this isolated worktree, and `test_isolation` confirms Bubblewrap cannot execute that missing in-sandbox interpreter. No Friday source was changed to work around this documentation-worktree environment mismatch.
- The verifier's four CLI help checks, `pip check` and tracked-generated-artifact scan passed separately after pytest stopped the verifier. No frontend source changed.

## Exact next implementation path

Begin Stage 33 discovery on stage-33/telegram-remote-owner-control after this design checkpoint is remotely recoverable. First qualify a disposable local-candidate topology for the poller, durable inbox/outbox, Telegram OwnerPrincipal and single-request lease without touching production. Then implement text conversation and bounded media through existing services; add task progress, explicit screen/desktop/coding routes and exact Stop; build and locally enroll the phone signer; qualify the production Friday-to-broker identity boundary; then run all 14 scenarios, full regressions, secret/integrity/recovery checks and controlled release gates. Do not start Stage 34 before Stage 33 completes its required acceptance and recovery gates.

## Known prerequisites and limits

- Owner must provision the bot token locally through the approved secret mechanism and perform numeric-ID/private-chat pairing.
- Owner phone OS/device must support the configured non-exportable P-256 signing key and device authentication; implementation needs a first-party signer client.
- Bot API update retention is at most 24 hours; offline commands beyond that window require resend.
- Production broker trust, local audio encoder, candidate-state isolation, service identity checks and recovery qualification remain unimplemented.
- All Telegram bot chat/media is cloud-chat data. Never send laptop passwords, reusable root credentials or bot secrets through Telegram.

No Friday, Qwen, UI, vision, wake, Anna, or administrator service restart is required for this documentation checkpoint. Keep Stage 32 running and intact.
