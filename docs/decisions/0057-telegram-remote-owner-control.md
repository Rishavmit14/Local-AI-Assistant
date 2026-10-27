# ADR 0057: Telegram Remote Owner Control

- **Status:** Proposed — Stage 33 design-ready; no implementation or deployment
- **Date:** 2026-10-27
- **Architecture:** [Telegram Remote Owner Control](../architecture/telegram-remote-owner.md)
- **Owner decision:** Stage 33 is Telegram Remote Owner Control. The prior screen-aware Career Forge recommendation is provisional Stage 34. Existing matrix rows 60 and 61 remain PARTIAL.

## Context

The Owner wants to reach Friday's local Ubuntu runtime from a private Telegram bot, including normal conversation, voice-note input/Anna output, continuity, screen awareness, desktop operations, coding tasks, progress, Stop, and owner-authorized local administration including root operations.

The integration must preserve the single local Qwen model, current Conversation and memory services, Career Forge/DLP rules, the existing Objective/TaskHistory/Gateway and Computer Agency records, cancellation/recovery, GitHub publication, proactive notifications, and Pocket/Anna. The Telegram bot credential must not become an execution credential.

The reviewed source establishes that production Owner-session APIs are bound to local Origin/CSRF/session controls. Telegram cannot be treated as a browser session. The current Owner Sovereign broker authenticates a candidate probe; production Friday is not yet trusted by the broker. Production broker trust is a Stage 33 prerequisite, not a current capability.

## Decision

1. Telegram is a private, single-Owner transport. Pair the bot locally to an exact 64-bit numeric Telegram user ID and private-chat ID, verify the bot ID, and reject groups, unknown users, bot senders, duplicates, stale requests, and unsupported update types before capability routing or media download.

2. Ubuntu initiates HTTPS long polling with Bot API getUpdates under a systemd user service. No webhook, inbound port, publicly reachable Friday API, Telegram Mini App, or group/inline/business access is required for initial core acceptance.

3. Persist a durable inbox, update cursor, idempotency keys, and delivery outbox. Advance Telegram's offset only after the corresponding inbox/admission record is durable. Use canonical Objective/task/action/notification IDs as idempotency and recovery authorities; never create an alternate executor or lifecycle ledger.

4. Add an explicit Telegram-origin OwnerPrincipal boundary. Derive it on the trusted Friday side from a verified paired update and service identity. Do not mint local browser cookies, CSRF values, Owner sessions or arbitrary caller-selected principal IDs. Keep channel provenance and route scope auditable.

5. Route text and transcribed voice through Friday's current ConversationService and LocalLLM/Qwen. Reuse current Whisper and Pocket/Anna boundaries. Anna renders without laptop playback and is encoded locally to a Telegram-supported voice format. Accept bounded photos and documents only through existing safe local perception/knowledge paths.

6. Route status, screen, desktop, coding, memory, learning, cancellation, progress, and notification work through their canonical service authorities. Preserve evidence/mastery policy, exact task-plan approval, fresh screen/action provenance, validation/review, durable cancellation and in_doubt recovery.

7. Keep the Bot API credential in local protected service credentials. The poller cannot access the administrator broker. Production Friday may use the broker only after exact production process identity is deliberately enrolled and independently qualified.

8. Require a signed, expiring, one-use phone approval for actions that existing consequence policy classifies as consequential. A first-party native phone client protects a non-exportable P-256 key behind device authentication. Friday signs the exact JCS canonical approval envelope, including Owner/chat, task/action, target, privilege class, nonce, expiry, preconditions, plan digest and exact operation digest. The phone displays signed fields and returns a signature through the bot. The trusted Friday process rechecks current plan/action state and nonce immediately before recording the canonical approval and dispatching through existing policy. Telegram buttons and natural-language acknowledgements do not substitute for the signature.

9. Use local systemd supervision, a single-instance lease, persistent cursors, stale-command suppression, reconciliation against canonical services, bounded retry/backoff, Telegram rate limits, and resource-aware single-owner request arbitration. Keep Stage 32 resource thresholds and production recovery behavior intact.

10. Defer Telegram Mini Apps. A future static/hosted Mini App may provide richer read/control views through Telegram's message/update path, but its initData must be server-validated and it may not grant authority or replace the phone signature. Bot API phone calls are not part of this interface; recorded voice-note turns are supported.

## Cryptographic approval envelope

Use RFC 8785 JSON Canonicalization Scheme for deterministic signed bytes. The challenge carries version, installation/key IDs, exact Owner and private-chat IDs, canonical objective/task/action/plan identity, operation and target summary, privilege/risk class, scope, preconditions, exact operation digest, 256-bit random nonce, issued/expires time, and approval purpose. Friday signs the challenge with its locally protected installation key. The paired phone verifies that signature and displays fields decoded from the signed envelope. After explicit Owner confirmation and device authentication, the phone signs the same canonical payload using its protected key. The trusted Friday process validates both identities, all bindings, expiry, unconsumed nonce and current exact plan digest. Any changed field invalidates the approval. Persist proof metadata and nonce consumption in the existing approval/audit authority, never the private key or a credential.

Default challenge lifetime is 120 seconds. A device without the configured hardware-backed key level cannot approve consequential actions. Exact replay of an already accepted response returns its receipt without re-executing; altered, expired or second-use approval is rejected.

## Consequences

- The Bot API's HTTPS long polling works behind ordinary outbound connectivity and avoids public Friday ingress.
- Telegram remains a cloud transport. Bot message content and attached media are disclosed to Telegram; the Owner must not send reusable passwords or secrets through the bot.
- The bot's long-poll cursor and 24-hour Telegram update retention require local durable state and explicit stale-message handling.
- A native phone signer is a Stage 33 component and requires a local one-time pairing. A Telegram Mini App alone is insufficient for cryptographic action approval.
- Production Owner Sovereign integration is not currently qualified. Stage 33 must add the production Friday process identity to the broker only with measured peer-authentication evidence, task-bound authorization, broker-secret isolation, audit, rollback and negative controls.
- The local audio encoder must be selected and pinned; FFmpeg was not present on PATH during design review.
- Existing owner-facing Career Forge work remains scheduled provisionally for Stage 34 and remains represented by matrix rows 60 and 61.

## Research and implementation references

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Telegram Bots FAQ](https://core.telegram.org/bots/faq)
- [Telegram Mini Apps](https://core.telegram.org/bots/webapps)
- [Telegram Privacy Policy](https://telegram.org/privacy)
- [Android Keystore](https://developer.android.com/privacy-and-security/keystore)
- [Apple Secure Enclave P-256 signing](https://developer.apple.com/documentation/cryptokit/secureenclave/p256/signing)
- [RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html)
- [Owner Sovereign Mode architecture](../architecture/owner-sovereign-mode.md)
- [Stage 32 release and recovery](../operations/stage32-release-plan.md)
