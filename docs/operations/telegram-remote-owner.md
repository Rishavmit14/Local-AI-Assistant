# Telegram Remote Owner Control — implementation and operations plan

**Status:** PROPOSED / DESIGN-READY. This is a runbook for the future Stage 33 implementation. No bot token, Telegram bot, service unit, phone approver, or production route is installed by this documentation change.
**Architecture:** [Telegram Remote Owner Control](../architecture/telegram-remote-owner.md)
**Decision:** [ADR 0057](../decisions/0057-telegram-remote-owner-control.md)

## 1. Readiness and scope

Stage 33 provides the Owner a private Telegram path into Friday's Ubuntu runtime. It includes text and recorded voice, existing memory/learning, explicit screen capture, bounded desktop and coding tasks, progress and cancellation, and consequential phone-signature approval for local administrator work. It preserves the ability to perform broad Owner-authorized computer operations, including privileged/root operations through Friday's trusted local broker.

Stage 33 is currently design-only. Do not treat this document as an installed service procedure. Stage 32's exact production source is 512d1d521b44b853d7ffebd62222e087b199c3a3, installed at the immutable release path in docs/operations/stage32-release-plan.md. During design review, the Friday API, Friday UI, Qwen supervisor and dependent Qwen UI were active. The protected /AI/projects/Local-AI-Assistant checkout contains owner-owned Pocket/Anna work. Do not use it as an implementation checkout.

Current prerequisites for implementation:

- A dedicated BotFather bot and fresh token provisioned locally; no token exists in this proposal.
- The Owner's numeric Telegram ID and private-chat pairing performed locally.
- A first-party signer client for the Owner's phone OS, using an authenticated non-exportable P-256 key; local installation-key and phone-key enrollment.
- A deterministic local audio encoder. FFmpeg was not found on PATH during design review; add and pin a local encoder or qualify another installed encoder before voice acceptance.
- A production-safe identity binding for Friday's API process to the existing administrator broker. The current broker trusts only the candidate qualification probe; production Friday must not be added to broker trust without candidate security qualification.
- Candidate-state copies, local secrets and service units under protected user/system state; none in Git or production before candidate gates pass.

## 2. Planned service boundary and setup sequence

The implementation should use one user-scoped poller service named friday-telegram.service, with a private credential and durable state under the owner's local state directory. It receives only update types required by the selected initial interface. It has no inbound listener and cannot reach the root broker. A private owner-only Unix socket carries typed update and notification DTOs between the poller and Friday. Friday verifies service identity and performs Owner pairing checks before constructing a Telegram channel principal.

Planned setup sequence:

1. Create the bot in BotFather, leave group privacy enabled, disable inline mode and group participation, and record the bot numeric ID locally.
2. Supply the bot token through the supported systemd credential facility for a user unit. If the installed user manager cannot provide a protected credential, use an owner-only local credential file outside Git. Never use an environment variable, command-line argument, Telegram message, task text, model prompt, or ordinary log for the token.
3. Install the local poller unit and private Unix socket with explicit systemd hardening, restart policy, resource limits, state directory and unit identity checks. The API accepts only the pinned poller unit and typed channel payloads.
4. Check getMe against the locally pinned bot ID. Check getWebhookInfo and require an empty webhook URL for long polling. If a stale webhook exists, stop and report it; deliberate removal must preserve pending updates.
5. From the Ubuntu local operator command, set the expected numeric Telegram user ID and begin a one-time pairing challenge. The Owner sends it from the private chat. Confirm exact sender/chat IDs locally; never auto-bind the first sender.
6. Pair the phone signer locally: pin Friday's installation public key, register the phone key using a short-lived challenge, verify the fingerprint, and record the key protection level. Reject consequential approvals when secure-key requirements are unmet.
7. Start the poller, verify a single active instance, validate the first persisted cursor and test /status from the paired private chat. Keep candidate learner, task and perception state isolated for qualification.
8. Run the acceptance scenarios in the architecture document. Only after candidate gates and recovery evidence pass should a separately reviewed release be prepared.

The poller should acquire one durable singleton lease before getUpdates. Use a long poll (nonzero timeout), batch size within Bot API limits, and a narrow allowed_updates list. Persist each update's idempotency and decision record before advancing the offset. The Bot API retains updates no longer than 24 hours; older requests are not recoverable. Enforce the local five-minute age limit on new work and 120-second approval-envelope expiry. Exact-ID Stop is safe only for a still-active exact canonical task and can be accepted for at most 24 hours.

## 3. Secret and state handling

Store runtime state outside the repository, for example under:

~~~text
~/.local/state/friday/telegram/
~~~

The implementation must create owner-only directories and files (directory mode 0700, files mode 0600), reject symlinks and unsafe ownership, and apply SQLite integrity checking and bounded retention. Keep database backups under the existing Friday maintenance/recovery policy. Do not include SQLite files or credentials in deployment packages, logs, source control, or Telegram attachments.

The durable inbox should contain a unique Telegram update ID, chat/message or callback ID, sender/chat binding result, timestamp, media metadata/digest, admission/rejection reason, stable idempotency key, canonical destination ID, and processing state. Do not retain full raw update JSON by default. Existing canonical services retain user conversation, memory, learning, task and action data.

The durable outbound queue should contain canonical notification/task identity, destination binding, bounded render state, retry schedule, and resulting Telegram message ID. It must never create or update a TaskHistory success state. Coalesce progress messages and respect Telegram's per-chat message rate guidance and retry_after values.

The phone approver stores only its private signing key in the phone keystore. Friday stores the registered public key and a private installation signing key outside Git in a restrictive local location. Rotation revokes the prior public key, invalidates outstanding nonces, preserves historical proof metadata, and requires a new local pairing. No signing key or challenge contains Bot API or laptop administrator credentials.

## 4. Runtime monitoring

Expose a read-only local health projection with:

- poller state, pinned bot identity match and last successful poll timestamp;
- single-instance lease state and durable update cursor;
- pending inbox/outbox counts and oldest age;
- Owner pairing status without printing account identifiers;
- phone-key fingerprint/status and outstanding challenge count;
- current request lease owner and canonical active task IDs;
- last network error class and retry-after duration, with Bot API token and full request URL redacted;
- resource-guard and production service health as distinct values.

Never expose this health projection publicly. A bot /status response is limited to the paired Owner and omits local paths, secrets, public-key material beyond a short fingerprint, process command lines and unrelated Owner data.

Progress and status are informational. Message delivery does not change canonical task state. If Telegram delivery fails, retain the outbox item and later report the existing task result once. Never claim that task success depends on a delivered message.

## 5. Rotation, revocation, and outage procedures

### Bot token rotation

1. Use BotFather locally to revoke/rotate the token.
2. Stop the poller so no process retains the old token.
3. Replace the local systemd credential or protected owner-only file without printing it.
4. Verify the bot ID with getMe; a different ID requires explicit local rebinding and Owner re-pairing.
5. Restart the poller and confirm one instance, empty webhook URL, correct cursor and a private Owner /status response.
6. Confirm logs, unit status, process arguments and audit contain no token or Bot API URL with token.

If rotation fails, keep remote ingress disabled and Friday's local services operating. Do not put the token in chat or request it from the Owner through Telegram.

### Bot revocation

Stop and disable the poller, remove its local credential, revoke the token in BotFather, invalidate the paired chat binding and outstanding approval challenges, and record the content-free revocation event. Friday's local UI, voice, Qwen, Memory, Career Forge and computer agency remain locally available. A Telegram command cannot revoke the administrator credential or self-pair a replacement bot.

### Phone key loss or compromise

Use the local pairing command to revoke the phone public key, invalidate every pending nonce, and require local enrollment of the replacement device. Do not accept a message or signature from the old key. If the phone account itself may be compromised, also rotate the Bot API token and rebind the numeric Owner account locally.

### Network outage or reboot

Keep the local runtime and canonical task records authoritative. The poller retries outbound HTTPS with exponential backoff and jitter. On restart it restores the durable update cursor and reconciles each inbox/outbox item to its canonical objective/task/notification ID. It does not reset offsets, drop all pending updates, create a new task, or replay an uncertain desktop/root/GitHub action.

Requests older than the configured age limit are rejected and the Owner is asked to resend. Telegram may discard updates after 24 hours. The bot reports unavailability while the laptop is offline; no remote command can run until connectivity and the local service return.

## 6. Candidate qualification and release recovery

Use a candidate runtime with copied schema and disposable learner/task/media state. Do not point candidate services at protected production databases. Verify source identity and package hashes before starting. Do not change the Stage 32 immutable release during candidate experiments.

For any future production activation:

1. Preserve the immutable Stage 32 release, current service configuration, all 15 database backups/integrity results, current learner/task/action fingerprints, and existing maintenance evidence.
2. Read the current Objective, Computer Agency, voice and in_doubt action state. Do not replay or delete the 12 historical in_doubt or three result_present actions recorded by Stage 32.
3. Qualify the candidate Telegram integration, production service identity, phone signer, administrator broker peer check, cancellation and recovery without production root mutations.
4. Run the full repository verifier, frontend checks if changed, relevant secret scan, package integrity, database migration checks, and the complete scenario matrix.
5. For production cutover, change only the reviewed Friday API/Telegram units needed for the accepted release. Do not restart Qwen, vision, wake workers, or Pocket/Anna unless a separately justified and qualified change requires it.
6. Back up state before any additive schema migration. Reconcile task and action records against canonical services before releasing a new process.
7. Verify API/UI/Qwen/vision and voice health, capture ownership, Anna selection, all database integrity, existing learner state and historical in_doubt/result_present counts. Confirm no replay, accidental task, or extra poller.
8. If the release fails, use the existing controlled service rollback/fix-forward procedure after checking for new writes. Never restore an old database backup over newer Owner data. Preserve unknown external effects for Owner review.
9. Record release SHA, branch/main refs, service identity, migration state, backups, verification and exact remaining blockers in CODEX_HANDOFF.md.

Stage 33 documentation registration does not deploy a service or alter this recovery point.

## 7. Acceptance evidence checklist

A qualification record must attach evidence for each scenario in [the architecture acceptance plan](../architecture/telegram-remote-owner.md#10-owner-phone-to-laptop-acceptance-scenarios):

- real paired Owner phone and private Telegram chat;
- exact identity and unauthorized sender rejection;
- canonical text and voice-note turns, with Anna playback on the phone;
- memory/learning continuity and explicit-mutation controls;
- fresh screen capture provenance and bounded desktop action verification;
- one coding objective through validation/review with exact task/commit identity;
- real progress delivery and active-task cancellation;
- valid privileged phone signature through the production-trusted Friday process and broker, plus tamper/replay/expiry negatives;
- stale/duplicate commands, restart/outage, bot/key rotation and revocation;
- CPU/memory/resource safety and protected production recovery;
- local-only secrets, redacted logs, no public listener and single poller;
- truthful failure, uncertainty, in_doubt and notification recovery.

A service health check, API test, simulated callback, or Telegram text reply alone cannot qualify any end-to-end scenario.
