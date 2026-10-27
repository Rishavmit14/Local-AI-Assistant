# Stage 33 — Telegram Remote Owner Control

**Status:** PROPOSED / DESIGN-READY — documentation only; no Telegram implementation, bot credentials, phone signer, service, or production change exists.
**Owner decision:** 2026-10-27
**Roadmap:** Stage 33. The earlier screen-aware Career Forge/DLP recommendation moves to provisional Stage 34. Matrix rows 60 and 61 remain PARTIAL and keep their existing identities.
**Decision record:** [ADR 0057](../decisions/0057-telegram-remote-owner-control.md)
**Operations and qualification:** [Telegram Remote Owner Control operations](../operations/telegram-remote-owner.md)

## 1. Goal and current truth

Friday is intended to remain the Owner's local personal cognitive operating system, reachable from the Owner's private Telegram chat while Friday runs on Ubuntu. Telegram is a remote interface to Friday's existing authorities. It must not become a second assistant, task ledger, executor, memory store, or source of intelligence.

The planned experience includes normal text conversation, recorded voice-note turns, Anna voice replies, memory and learning continuity, explicit screen capture, bounded desktop work, coding objectives, progress, cancellation, and owner-authorized privileged operations. The design preserves broad Owner-authorized computer operation, including root operations mediated by Friday's trusted local administrator broker.

The product capability itself is currently ABSENT. Friday has no Telegram bot integration or phone approval client. Stage 32 is QUALIFIED and DEPLOYED, but its production API process is not yet trusted by the Owner Sovereign administrator broker. The current broker qualification is bounded to a candidate probe. Production trust integration and its security qualification are explicit Stage 33 work, not an assumed capability. See [Owner Sovereign Mode](owner-sovereign-mode.md), [ADR 0033](../decisions/0033-owner-sovereign-administration.md), and matrix row 59.

## 2. Architecture

~~~text
Owner phone
  Telegram private cloud chat
        |
        | HTTPS Bot API getUpdates (outbound long polling)
        v
friday-telegram.service
  private Bot API credential
  durable inbox / update cursor / delivery outbox
  no desktop, shell, model, memory, or administrator-broker authority
        |
        | owner-only Unix socket; pinned service identity; typed DTOs
        v
Friday local runtime
  Telegram-origin OwnerPrincipal after server-side binding checks
  existing ConversationService + local Qwen
  existing Memory, Career Forge, Learning Paths and Proactive Events
  existing Objectives + TaskHistory + Gateway + isolation / validation / Git
  existing Perception + DesktopControl + Computer Agency
  existing Pocket/Anna output and speech transcription boundaries
        |
        | only after existing task policy and bound phone approval where required
        v
trusted production Friday process
        |
        | exact process identity over private Unix socket
        v
Owner Sovereign administrator broker
  credential remains inside trusted broker; no Bot API access to root credential
~~~

All Friday and broker communication stays on the laptop. The bridge has no public listener. Telegram's Bot API is the only required remote transport; it is not a proxy for Friday's localhost API. The poller uses HTTPS to Telegram and a private local Unix-domain socket to exchange typed requests and notifications with Friday. The socket is owner-only, and the receiver validates the peer process/unit identity. No arbitrary URL, HTTP callback, shell string, filesystem path, authorization header, or caller-selected principal is accepted as a general-purpose API.

The poller and Friday runtime use a single-instance lease. The poller is supervised by its own systemd user unit, persists its inbox cursor, and retries network failures with bounded exponential backoff and jitter. Friday's existing API/UI, Qwen, vision, wake, and Pocket/Anna lifecycles remain independently supervised. A bridge restart must not imply a Friday, Qwen, voice-worker, or desktop restart.

## 3. Owner identity, pairing, and command admission

Pairing is completed from the local Ubuntu account. The Owner pins the expected 64-bit numeric Telegram user ID, then proves control of a Telegram private chat using a random, single-use, short-lived local pairing challenge. The resulting private chat ID is bound to that exact numeric user ID. The Bot API bot identity from getMe is also pinned. Pairing never means trust the first account that messages the bot.

Every incoming action-bearing update must satisfy all of these checks before content is passed to a Friday capability:

1. It is a supported update type and its sender is not a bot.
2. Chat type is private. The message chat ID equals the pinned private chat ID and sender ID equals the pinned numeric Owner ID.
3. The bot ID matches the locally pinned Bot API identity.
4. Its update ID and, where present, the chat/message or callback-query ID have not been admitted before.
5. The message date is valid and within the action's age window. New conversation or action requests older than five minutes are rejected with a resend prompt. An exact-ID Stop may be accepted for up to 24 hours, but only while that exact task or turn is still cancellable; Stop never means cancel whichever work is current.
6. Rate limits, payload sizes, media limits, active-owner-request admission, and current service health pass.
7. Authorization is derived server-side from the validated Telegram update and persisted pairing. Caller-supplied Owner IDs, bot usernames, display names, message text, model output, or local session cookies cannot create authority.

The local Owner browser session in [local_owner.py](../../src/local_ai_assistant/interface/local_owner.py) remains a distinct credential. Telegram does not synthesize its cookie, CSRF value, Origin, or local-owner grant. The adapter introduces a typed Telegram channel principal that maps to the same stable local Owner identity while preserving channel provenance and a narrow route scope. The receiving service performs identity checks itself; the bridge cannot ask the service to trust an arbitrary principal.

Routine unauthorized updates are rejected before media download, conversation routing, task creation, or private-data reads. Store content-free audit facts: update ID, message ID, numeric actor/chat binding result, type, timestamp, payload digest, admission decision, rate decision, and canonical conversation/objective/task/action/notification IDs when one exists. Do not copy full Telegram history into a competing transcript database. Existing Conversation, Memory, Career Forge, Objectives, TaskHistory, Computer Agency, and Proactive Event stores retain the content and state they own.

## 4. Canonical service integration

| Telegram request | Canonical authority and route | Required behavior |
|---|---|---|
| Text question or follow-up | Same FridayConversationService used by the local product; same configured LocalLLM/Qwen client and conversation-session boundary | Keep single-Owner context coherent across approved channels. Attach source channel and conversation-turn IDs. An interaction lease arbitrates against voice/UI work; busy means queue or report busy, never run hidden concurrent inference. |
| Voice note | Existing Whisper transcription boundary, then the same FridayConversationService | Download only after owner authorization; decode locally; retain no unrequested raw audio. Treat transcription as user input, not machine-verified identity. |
| Memory recall, remember, forget | Existing FridayMemoryService and its explicit owner-intent/provenance rules | Share existing local Owner memory. Do not create Telegram-only memory or infer durable facts from ordinary chat. |
| Learning-path or Career Forge interaction | Existing LearningPathService, CareerForgeService, assessment, Reviewer, and evidence/mastery contracts | Use the authenticated Telegram channel principal at the existing service boundary. Preserve path/version/node/mission, assistance, attempt, evidence, review, and one-rung mastery rules. A task result or Telegram button cannot grant mastery. |
| Desktop status, screenshot, observation, or app operation | Existing Perception, DesktopControl, ComputerAgencyController, ledger, GNOME permission and observation-verification paths | Preserve exact target and fresh observation IDs, permission results, task/action IDs, and postcondition. A screenshot is an explicit Owner-requested transfer to Telegram. Phone-uploaded pictures are owner-provided media, never provenance for a current laptop screenshot. |
| Coding or multi-step request | Existing ObjectiveService → TaskHistory/Gateway → approved isolated worktree → validation/review/recovery path | Reserve one canonical objective/task idempotently. Review and approve the exact current plan through the existing authority. Preserve publication scopes and exact GitHub transport and verification. |
| Stop/cancel | Existing voice-turn cancellation, ObjectiveService, TaskHistory/Gateway and Computer Agency durable cancellation APIs, addressed by exact canonical ID | Record Stop intent immediately, stop active local generation/action cooperatively, and do not relabel an uncertain external effect as cancelled. Never replay an in-flight action after restart. |
| Progress and proactive notification | Existing task/objective/action state and ProactiveEventEngine, with a delivery-only Telegram outbox | Progress is a projection of canonical state. The Telegram outbox tracks delivery IDs only; it cannot mark a task successful or alter its source state. |
| Privileged operation | Existing policy/controller and TaskHistory action; existing trusted Friday service uses PrivilegedExecutor and root broker | Extend the broker's allowlisted peer identity only after production integration is qualified. The Telegram process never opens the broker socket, reads the administrator credential, or executes privileged commands. |

Stage 32 source already uses the canonical Conversation, voice-learning, Objectives, TaskHistory, Computer Agency, Perception, and Pocket/Anna paths. Current owner-session endpoints, exact local request origin, exact-plan approval, action recovery, and broker peer identity remain authoritative. New channel wiring extends these boundaries explicitly. Relevant code includes [ConversationService](../../src/local_ai_assistant/interface/conversation.py), [ObjectiveService](../../src/local_ai_assistant/autonomy/service.py), [ComputerAgencyController](../../src/local_ai_assistant/desktop/agency.py), [its ledger](../../src/local_ai_assistant/desktop/agency_ledger.py), and [the administrator client](../../src/local_ai_assistant/admin/client.py).

## 5. Consequential-action approval from the phone

Telegram identity alone does not approve consequential work. Inline buttons, reply keyboards, callbacks, and natural-language yes are requests that Friday must revalidate; none is a cryptographic approval.

The first core implementation includes a minimal first-party phone approval client, not a Telegram Mini App. The client stores a non-exportable NIST P-256 signing key in the phone's secure keystore and requires device authentication for each approval. Android Keystore and Apple Secure Enclave provide platform facilities for protected P-256 signing; hardware-backed status is device-dependent on Android. The client must report its key protection level, and a device that cannot meet the configured secure-key policy cannot approve consequential operations.

At local pairing, the Owner pins Friday's installation signing public key and registers the phone public key through a one-time local enrollment challenge. For each action requiring confirmation, Friday sends a canonical approval envelope as a Telegram attachment. The envelope is versioned canonical JSON using [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785.html), signed by Friday, and includes:

- Friday installation ID and phone key ID;
- exact numeric Telegram Owner ID and bound private-chat ID;
- canonical objective, task, action, and plan identity where applicable;
- action, target, privilege class, scope, parameters summary, and expected effect;
- exact SHA-256 digest of the operation/plan bytes that the trusted executor will use;
- exact preconditions and consequence/risk class;
- cryptographically random 256-bit nonce, issue time, expiry time, and approval purpose.

The phone client verifies Friday's signature, checks expiry and paired installation, and derives its human-readable display from the signed fields. It presents every executable/argument or plan step, the full target, affected repository/paths or local resources, privilege class, expected effect, rollback availability, and exact operation digest. An opaque digest without a readable exact action is not approvable. After explicit Owner confirmation and phone unlock, the phone signs a domain-separated approval response containing the canonical envelope digest, Owner/chat binding, decision, nonce and action identity. Friday verifies the registered phone signature, Owner/chat binding, nonce, expiry, task/objective/action binding, and current plan digest immediately before the existing executor records approval. Any plan, target, argument, privilege, or precondition change invalidates the envelope and requires a new review.

Use ECDSA P-256 with SHA-256 for both installation and phone signatures, with distinct domain-separation labels for challenge and approval. The signed operation manifest is canonical RFC 8785 JSON and includes exact executable/argument or plan identity, target, scope, privilege class, preconditions and the operation digest. It contains no secret input; the approval client renders all human-actionable fields before showing the device-authentication prompt.

Default approval expiry is 120 seconds. A consumed nonce is durably single-use. Exact replay of the same accepted response returns its existing receipt/result without repeating execution; a changed or reused response is rejected. The existing canonical approvals/audit record retains signer key ID, envelope digest, exact operation digest, timestamps, verification result, and canonical task/action IDs. Neither the Bot API credential nor laptop administrator credential appears in the envelope, phone client, Telegram reply, ordinary logs, model context, source control, or audit text.

Root privilege itself is not a confirmation trigger. Friday continues to apply the existing consequence, ambiguity, scope, and reversibility policy. Low-risk, clear Owner requests should not gain a redundant confirmation loop; irreversible, destructive, privacy-sensitive, external, or otherwise consequential work follows the exact signed approval path. Phone approval supplements the existing authorization, plan, isolation, validation, rollback, and broker checks; it does not replace them.

## 6. Text, voice, audio, photo, and document handling

All accepted media is bounded and decoded locally. The Telegram hosted Bot API currently limits bot file downloads to 20 MB. Bot API uploads currently allow up to 50 MB; Stage 33 should choose stricter configurable per-type limits and never rely on the platform maximum as a safety limit. Check the current [Bot API file documentation](https://core.telegram.org/bots/api#sending-files) again during implementation.

- Text is plain text by default. Split responses at Telegram's current 4096-character message limit on safe boundaries. Do not interpret formatting entities or embedded URLs as authority.
- Voice notes use Telegram's recorded Voice update. Validate declared and actual size, content signature, duration, sample rate and channels; decode inside a private bounded temporary directory through a fixed local decoder invocation. Reject malformed, over-duration, over-size and unsupported media before transcription. Feed the normalized waveform into Friday's current Whisper boundary.
- Incoming audio attachments may use the formats the pinned local decoder can safely handle, within the same duration and byte caps. Do not accept arbitrary video, executable, archive or nested-container extraction in the first version.
- Anna replies render through Friday's existing Pocket/Anna voice provider without opening the laptop speakers. Convert the returned local audio using a fixed, sandboxed, timeout-bounded local encoder to Ogg/Opus and send it through sendVoice. Current official Bot API documentation accepts Ogg/Opus, MP3 or M4A for voice messages. The inspected host does not currently have FFmpeg on PATH; Stage 33 must provision and pin a local encoder such as FFmpeg, or qualify an already-installed deterministic encoder, before voice acceptance. No cloud conversion service is allowed. Keep the text response available if voice encoding or upload fails.
- Photos are downloaded only from an authorized Owner update, size checked before and during transfer, content-sniffed, and passed to existing local perception/vision handling as an owner-supplied image. An uploaded image does not become a live desktop observation.
- Documents are bounded and accepted only for explicit supported local extraction/attachment paths. Use extension and content checks, quarantine private temporary files, never execute attachments or auto-install packages, and pass extracted text as untrusted data to existing Knowledge/Conversation boundaries. Preserve filename, source-message and content-digest provenance; avoid storing the Telegram file URL or bot token.

Use restrictive file modes and short retention for conversion files. Delete temporary media after the required service finishes or on restart cleanup. Keep only content-free intake audit metadata unless an existing authoritative subsystem deliberately retains the user's input under its documented rules.

## 7. Status, progress, and task control

Use one durable progress message per active canonical task where possible. Update it from current Objective/TaskHistory/Computer Agency events at a bounded rate. Queue durable completion/failure notifications in the local outbox while Telegram is unavailable; send once and record the resulting Telegram message ID. Respect Telegram's retry_after response and current per-chat rate guidance. Coalesce frequent progress changes rather than producing a message per tool event.

The current Bot API offers sendMessageDraft for a temporary preview of up to 30 seconds. A draft is not a persisted result; Friday must send the completed response with sendMessage. Draft stop events cancel only the exact associated generation/task after identity and state checks. Long-running actions use an exact-ID Stop action bound to their canonical task. A visible Stop control is not proof of cancellation. Friday reports cancelled only after its canonical source confirms cancellation; uncertain external effects stay in_doubt/recovery_required and remain visible for reconciliation. The Telegram Bots FAQ advises against sending more than one message per second in a single chat; Stage 33 enforces that private-chat rate and honors retry_after instead of retrying in a tight loop.

A Telegram delivery failure does not undo or relabel a completed laptop operation. Friday records delivery state separately and reports the exact canonical outcome when communication resumes.

## 8. Restart, outages, privacy, and resource policy

The Bot API supports either getUpdates long polling or setWebhook; they are mutually exclusive. Webhooks require Telegram-reachable public HTTPS ingress and a supported public port. Stage 33 uses outbound long polling by default, and Friday exposes no public listener. At startup the bridge confirms the pinned bot identity and verifies that no webhook is configured. If a stale webhook exists, setup reports it for deliberate removal without dropping pending updates.

Telegram updates are retained by Telegram for no more than 24 hours. Update IDs usually increase sequentially, but Telegram may choose a random next ID after a week with no updates. Persist each update ID and recompute getUpdates offset from each response. If the poller has been idle for at least a week and has no locally unacknowledged update, make one resynchronizing getUpdates request without the old numeric offset; Telegram has already expired older updates. Deduplication records prevent repeat effects, and the next offset is derived from the returned batch. Do not use a negative offset or drop_pending_updates. In one local transaction, write the deduplication key, content digest, admission result, stable idempotency key and pending canonical operation before advancing the persisted offset. Use canonical service idempotency keys so a crash between ingress and response cannot create a second Objective/task. A non-owner update can be durably rejected and acknowledged without executing or downloading media.

After reboot, the bridge resumes from its saved cursor, reconciles pending inbox/outbox rows against their canonical IDs, and suppresses stale work by message date and action-specific age limits. Requests missed beyond Telegram's 24-hour retention are lost; the Owner resends. No queued work begins automatically if the local clock is unhealthy, identity/pairing is unavailable, the request lease is held, production health is degraded, or a recovered task has uncertain effects.

Telegram private bot conversations are cloud-chat traffic, not an end-to-end encrypted Secret Chat. Telegram states that cloud-chat messages are stored on Telegram servers and that Bot API users share the messages/media they send with the bot developer. The Owner must treat text, voice, screenshots, photos, documents, transcripts, and approval envelopes sent through Telegram as data disclosed to Telegram's cloud service. Do not transmit laptop/root passwords or reusable credentials. The bot is private and never joins groups; privacy mode stays enabled.

A later Telegram Mini App is optional and does not expose a Friday HTTP endpoint. It sends requests back through Telegram updates. If added, the server validates Telegram.WebApp.initData with the Bot API HMAC-SHA-256 procedure and a strict auth_date window; initDataUnsafe is never trusted. This web identity check grants only the same paired channel scope and never replaces phone-key approval.

The runtime keeps the accepted single-general-purpose-model architecture: local Qwen remains the only general-purpose reasoner; voice transcription, Anna, existing local vision and deterministic parsers are reused. One request lease spans local conversation, voice and Telegram to prevent duplicate simultaneous Owner jobs and avoid resource contention. Under pressure, admission reports unavailable/busy and preserves the request without silently starting background inference. Resource recovery retains the Stage 32 guard thresholds and production recovery procedure.

## 9. Telegram capability and limitation matrix

| Capability | Stage 33 core target | Limit or boundary |
|---|---|---|
| Private bot pairing | One bot, one pinned Telegram numeric Owner ID and one bound private chat | No username-only identity, group, channel, inline, business-chat or multi-owner access |
| Text conversation | Existing canonical conversation and shared bounded Owner context | Message age, rate, 4096-character output and one-request arbitration |
| Recorded voice note | Existing local transcription → Conversation → Pocket/Anna render → Ogg/Opus sendVoice | Turn-based only; inbound hosted Bot API download limit currently 20 MB; bounded duration and local decode |
| Audio/photo/document | Explicit supported media paths with local inspection and provenance | No arbitrary archive extraction, executable processing, video-call stream or automatic import |
| Screen status and screenshot | Explicitly requested fresh local capture and provenance-bound send | Not a phone camera photo; screenshot is uploaded to Telegram cloud |
| Desktop/application work | Existing Computer Agency with fresh targets, permissions, verification and durable action history | No competing executor, no blind clicks, no replay of uncertain actions |
| Coding tasks and publication | Existing Objective/TaskHistory/Gateway and isolation/validation/review/GitHub publication scopes | Exact plan and repository binding; public publication retains its existing approval boundary |
| Consequential operation approval | Signed, expiring, single-use phone signature over exact operation digest | Requires enrolled phone signer and trusted production broker; Telegram button/text alone never approves |
| Root/administrator operation | Full Owner-authorized local broker-mediated capability | No bot token to broker, no password in Telegram, no global NOPASSWD or raw model shell authority |
| Progress and notifications | Canonical task state plus durable bounded outbox | Delivery is best effort during outage; Telegram rate limits apply |
| Stop | Exact active turn/task ID, durable cancellation request and canonical outcome | No broad stop-latest; in_doubt external results are not represented as cancelled |
| Offline laptop | Local work and history remain local; poller reconnects when network returns | No remote chat while laptop or internet is offline; updates expire after at most 24 hours |
| Telegram Mini App | Optional later rich status/control surface | Not required for initial acceptance; initData must be verified and never substitutes for phone-key approval |
| Native real-time Telegram phone call | NOT SUPPORTED | The reviewed Bot API documents recorded audio/voice messages but no private real-time call/join API. Stage 33 accepts voice notes only. |

## 10. Owner phone-to-laptop acceptance scenarios

Each scenario is run first on an isolated candidate with disposable state. Final channel acceptance uses the real Owner phone and real Telegram account against the qualified candidate, with no owner-data migration or live privileged mutation. Any production activation is a separate controlled release with current backups and fresh safety/recovery checks. The Stage 32 production evidence and historical in_doubt actions are read-only.

### 1. Pairing and authorization

- **Request:** Owner sends the local one-time pairing challenge from the intended Telegram account.
- **Authority/effect:** Locally pinned numeric Owner ID, Telegram bot ID, random expiring challenge, and private-chat binding; persist one exact pairing.
- **Evidence:** Masked status showing paired/not-paired, key fingerprints, private-chat binding hash, event IDs, and no token/key material.
- **Negative controls:** Different numeric ID, changed chat, group, bot sender, expired challenge, second-owner attempt, and repeat pairing do not create or replace the binding.
- **Recovery:** Re-pair only from the local Ubuntu command; revoke the prior binding and phone key, invalidate pending nonces, then reconcile cursor/outbox.
- **PASS:** Only the locally paired numeric Owner in the bound private chat can reach an Owner route.

### 2. Text conversation

- **Request:** Send a normal question and a follow-up referring to the prior turn.
- **Authority/effect:** Same FridayConversationService, session policy, LocalLLM/Qwen and interaction lease; return an answer with truthful channel/turn identity.
- **Evidence:** Correlated update, Conversation turn, local model request and final Telegram message IDs.
- **Negative controls:** No cloud model, fabricated action result, parallel second inference, unauthorized prompt or task mutation.
- **Recovery:** Restart the candidate service and verify active-session reset or durable Memory recall only according to the existing service contract.
- **PASS:** Correct answer and context continuity; no duplicate turn or unauthorized state write.

### 3. Voice note and Anna reply

- **Request:** Send a recorded Telegram voice note asking Friday a simple question.
- **Authority/effect:** Authorized media intake → bounded local decode → existing Whisper transcription → canonical Conversation → Pocket/Anna render-only synthesis → local Ogg/Opus conversion → Telegram sendVoice; laptop speakers remain idle.
- **Evidence:** Media digest/size/duration, transcription and Conversation IDs, selected Anna provider, encoder exit/format probe, Bot API message ID and phone playback confirmation.
- **Negative controls:** Oversize, malformed, unsupported, empty, excessive-duration and unauthorized audio never reaches transcription; no model/provider substitution.
- **Recovery:** Delete candidate temporary audio on completion and restart; text answer remains available if encoding/upload fails.
- **PASS:** Owner hears Anna voice-note playback on the phone; no desktop playback or production voice change.

### 4. Memory and learning-context continuity

- **Request:** Establish a test fact, explicitly ask Friday to remember it, start a disposable Career Forge lesson, then ask for recall/progress from Telegram.
- **Authority/effect:** Existing Memory capture/retrieval and existing LearningPath/CareerForge mission, assessment and progress contracts.
- **Evidence:** Memory provenance and read-after-service-restart result; same path/version/node/mission and assistance/evidence IDs across Telegram and local Astra.
- **Negative controls:** Ordinary chat does not create a memory; phone-provided text cannot grant mastery; incorrect/uncertain answer creates no qualifying evidence; no second learner database.
- **Recovery:** Candidate restart reconstructs only durable Memory/Learning state; unsubmitted answer draft remains discarded under current semantics.
- **PASS:** Friday recalls only the explicitly stored test fact and displays canonical learner progress without changing mastery by conversation alone.

### 5. Screenshot and screen explanation

- **Request:** Owner asks for a fresh laptop screenshot and a concise explanation.
- **Authority/effect:** Owner-authenticated existing ScreenCaptureService and current local interpretation; send the exact captured pixels to the paired private chat.
- **Evidence:** Capture ID/time/source, pixel digest, retention record, explanation turn and Telegram upload message ID.
- **Negative controls:** No capture on implicit/background request; stale capture, private path disclosure, phone camera photo mislabeled as laptop state, or model-inferred screen content without pixels.
- **Recovery:** Candidate retained image expires and is deleted under the configured private retention rule; audit keeps the capture ID/digest only.
- **PASS:** Phone receives the same fresh capture Friday interpreted, and the explanation separates observed pixels from inference.

### 6. Bounded desktop operation

- **Request:** Ask Friday to open a known installed application or permitted website.
- **Authority/effect:** Existing ComputerAgencyController, task/action ledger, GNOME permission, target resolver and fresh postcondition verifier.
- **Evidence:** Canonical task/action IDs, target identity, permission outcome, observation ID, verified state and exact Telegram result.
- **Negative controls:** Stale target, missing permission, ambiguous target and unpaired request cause no dispatch; no direct shell, raw coordinates, second executor or unsupported external app action.
- **Recovery:** Cancel by exact task ID; preserve uncertain actions for existing reconciliation and never automatically replay.
- **PASS:** The requested target opens and Friday reports success only after the canonical observation verifies it.

### 7. Coding task initiation and verified outcome

- **Request:** Submit a bounded coding task against a disposable configured repository and request status.
- **Authority/effect:** ObjectiveService reserves one objective/task; Gateway creates the exact plan; Owner reviews/approves through the existing authenticated plan authority; isolated execution, tests, review and Git result stay canonical.
- **Evidence:** Objective/task IDs, exact plan hash, approvals, worktree/commit SHA, validation/review records and final status returned to Telegram.
- **Negative controls:** Duplicate update does not create a second task; missing repository, stale plan, denied scope or failed validation cannot produce success or publication.
- **Recovery:** Restart candidate API/bridge; reconstruct the same objective and task. Preserve any incomplete/in_doubt external action for review.
- **PASS:** One task reaches the exact verified terminal state; no pull request/publication occurs unless its distinct existing approval is present.

### 8. Progress and Stop/cancel

- **Request:** Start a bounded long-running candidate task, inspect Telegram progress, then issue Stop with its exact ID.
- **Authority/effect:** Canonical objective/task/action state; Telegram progress is a projection. Stop writes existing durable cancellation intent and signals the active worker.
- **Evidence:** Ordered task events, update/outbox/message IDs, cancellation-request and terminal events, no stale model/tool output after cancellation.
- **Negative controls:** Wrong/terminal ID, duplicate Stop, no-ID broad Stop and unrelated callback cannot stop another task or mark it cancelled.
- **Recovery:** Restart while cancellation is pending; recover by canonical ID and retain any uncertain external side effect in_doubt/recovery_required.
- **PASS:** Active work receives real cancellation; response distinguishes cancelled, too late, already terminal, and uncertain external effect truthfully.

### 9. Privileged-operation approval and execution

- **Request:** On a disposable candidate, request one reversible root-owned operation inside a dedicated temporary path and approve its displayed challenge on the phone.
- **Authority/effect:** Existing consequence policy and TaskHistory action; Friday-signed exact operation envelope; enrolled hardware-backed phone signature; production-equivalent trusted Friday process identity to the root broker.
- **Evidence:** Envelope and plan digests, nonce/expiry/key ID, phone authentication event, canonical approval record, broker peer identity, bounded operation result and audited cleanup.
- **Negative controls:** Altered target/argument/digest, wrong phone key, invalid/expired/replayed signature, changed plan, wrong Owner/chat, missing broker trust and direct poller socket access are denied before privileged dispatch.
- **Recovery:** Broker restart or network loss does not repeat execution; re-read canonical action; remove the disposable file through an explicitly authorized cleanup; preserve unknown result for Owner review.
- **PASS:** Exact signed operation runs once through the broker and verifies; laptop/admin password, bot token and raw credential never reach Telegram or model/audit text.

### 10. Rejected unauthorized message

- **Request:** A second Telegram account messages the bot and sends a photo/document.
- **Authority/effect:** No Owner principal is constructed; record only bounded rejection metadata and optionally return a generic unavailable response.
- **Evidence:** Rejected update ID and reason code; unchanged conversation, memory, tasks, files and screen captures.
- **Negative controls:** Username/display-name match, group command, forged callback, replayed pairing token and oversized media do not pass admission.
- **Recovery:** No privileged cleanup is necessary; rate-limit abusive senders without exposing the pinned Owner ID.
- **PASS:** No file download, private read, LLM request, task creation, notification acknowledgement or action occurs.

### 11. Expired and duplicate command protection

- **Request:** Replay the same Telegram update, resend the same message, submit an over-age task command, and replay a consumed approval response.
- **Authority/effect:** Unique inbox keys plus message/callback/nonce deduplication; action-specific timestamp windows and canonical idempotency keys.
- **Evidence:** Single admission/decision, duplicate/stale reason, one canonical task ID and no second side effect.
- **Negative controls:** Clock drift, future timestamp, random update-ID jump after a quiet week, duplicate batch and expired challenge fail closed.
- **Recovery:** Preserve cursor and idempotency records across database/service restart.
- **PASS:** New work executes at most once; stale work requires resend; exact-ID Stop follows only its bounded safe rule.

### 12. Restart and network-outage recovery

- **Request:** Start a candidate task, disconnect outbound network, restart the poller/API, restore the network, and send a new request.
- **Authority/effect:** Durable SQLite inbox/cursor/outbox, systemd-supervised poller, canonical TaskHistory/Objective/GCA recovery and one-owner lease.
- **Evidence:** Unit restart timeline, offset/cursor, received update IDs, outbox reconciliation, one active request, unchanged task/action identities.
- **Negative controls:** No webhook or inbound port; no backlog flood, stale command, duplicate Qwen task or automatic in_doubt replay; updates beyond Telegram's retention are not assumed recoverable.
- **Recovery:** Exponential retry, startup reconciliation, exact task-history read, and owner-visible resend request for lost/stale updates.
- **PASS:** Service returns to polling; one new fresh command is handled once and older commands do not start.

### 13. Safe credential rotation and revocation

- **Request:** Rotate the Bot API token in the local credential store, restart the candidate bridge, then revoke it; separately revoke and re-enroll the phone approval key.
- **Authority/effect:** BotFather controls Bot API token lifecycle; local operator replaces the credential and verifies bot identity. Local pairing authority rotates approval keys and invalidates outstanding nonces.
- **Evidence:** Secret-store metadata/version only, getMe bot ID match, no token in service status/logs/argv, old-token rejection, key fingerprint transition and audit event.
- **Negative controls:** Mismatched bot ID, revoked phone key, old signed envelope, token in environment/command line/audit and remote self-pairing fail.
- **Recovery:** Restore the last known secret locally if rotation fails, or keep polling disabled until a valid token is installed. Lost phone key requires local re-pairing.
- **PASS:** Rotation restores polling without changing Owner binding or tasks; revocation disables remote ingress/approval and leaves Friday's local operation intact.

### 14. Resource pressure and production recovery

- **Request:** On candidate hardware state, apply bounded CPU/memory pressure while checking local Qwen, voice, Telegram responsiveness, and task recovery; then restore the candidate.
- **Authority/effect:** Existing Stage 32 resource policy and candidate service supervisors; no new general model or concurrency path.
- **Evidence:** PSI/memory/worker health, admission decisions, Telegram queue age, Qwen request count, Pocket/Anna state, database fingerprints, service identity and independent restoration report.
- **Negative controls:** Do not weaken thresholds, restart Qwen/vision, steal microphone ownership, launch an extra model, replay any historical in_doubt action or write candidate data into production.
- **Recovery:** Stop pressure safely, restore the exact prior release/services using the controlled procedure, verify databases and wake/capture/Anna health, and keep uncertain actions untouched.
- **PASS:** Candidate defers work under pressure, returns healthy after recovery, and protected Stage 32 release, services, Owner data and historical in_doubt actions remain unchanged.

## 11. Official platform research

Reviewed 2026-10-27 against official Telegram Bot API documentation and official Telegram privacy material. Bot API methods and platform limits change; implementation must recheck these sources and update this document before shipping:

- [Telegram Bot API: updates, getUpdates, webhook and update retention](https://core.telegram.org/bots/api#getting-updates)
- [Telegram Bot API: file downloads and uploads](https://core.telegram.org/bots/api#sending-files)
- [Telegram Bot API: sendVoice, sendMessageDraft and update types](https://core.telegram.org/bots/api)
- [Telegram Bots FAQ: privacy mode, file limits and rate guidance](https://core.telegram.org/bots/faq)
- [Telegram Mini Apps: initData validation](https://core.telegram.org/bots/webapps)
- [Telegram Privacy Policy: cloud chats and bot messages](https://telegram.org/privacy)
- [Android Keystore system](https://developer.android.com/privacy-and-security/keystore)
- [Apple Secure Enclave P-256 signing](https://developer.apple.com/documentation/cryptokit/secureenclave/p256/signing)
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html)
