# ADR 0055: Bind voice learning to canonical learner state

- **Status:** Accepted for Stage 32 code-only qualification
- **Date:** 2026-10-16

## Context

Stage 31 supplied an active, versioned DLP path, fixed lesson assessment
contracts, Career Forge dynamic subjects, evidence-backed mastery, and an
Owner-authenticated Learn interface. Friday already owns wake detection, final
ASR, local Qwen roles, Pocket/Anna speech, AEC, barge-in, explicit Stop, and a
runtime event stream. Voice needed to invoke those existing authorities without
creating a second learning store, bypassing Owner authorization, or making a
confirmed assessment impossible to distinguish from a pending transcript.

The local Owner voice principal is available through `LocalOwnerTrust` only
when the private local capability is present. Browser reads and mutations have
their separate Owner-session, loopback Host, Origin, and CSRF boundary. A Stop
can overlap Qwen or Reviewer work, including the instant between Reviewer
completion and assessment persistence.

## Decision

Route learning commands only on voice-origin conversation turns, before generic
capability adapters. `VoiceLearningCoordinator` reads the selected active DLP
path/version, its current eligible node, Career Forge session, and fixed
assessment contract. It may start or resume the matching dynamic lesson, but
must not create/select a path or create a Project. Teach only authored lesson
content and its exact contract question through the existing local Qwen role.
Use the existing TEACH_BACK Reviewer and `GeneralizedLearningService` for
assessment, evidence, mastery, remediation, and prerequisite progression.

Keep one bounded final-transcript answer draft in process memory. A correction
replaces that draft. Explicit Owner confirmation submits it exactly once under
the draft's random interaction id. Cancel and exact Stop discard unsubmitted
text. A confirmed attempt survives later Stop; cancellation before the
assessment commit leaves the attempt pending without evaluation/evidence. The
turn marker remains associated with the Reviewer through this commit boundary,
and next-question selection is reconstructed from canonical successful fixed
question IDs if a mission resume hint is stale.

Publish path/node context and transient draft/assessment state through the
existing runtime event stream. The frontend follows that identity into Learn,
stores only an unsubmitted transcript draft in runtime memory, and refreshes
canonical learner state on feedback. No new daemon, model, database, endpoint,
cookie/CSRF shortcut, wake engine, or persistent transcript is introduced.

AEC interruption may listen during the bounded model/Reviewer wait before first
playback, then use the existing stream-cancel and playback-stop contracts.
When the active-task Stop reader already owns capture, do not start the second
reader. Preserve the legacy playback-only fallback if idle AEC capture is not
available.

## Consequences

- Voice and Learn derive progress from the same DLP and Career Forge records.
- Failed/uncertain review creates no mastery evidence; a successful answer
  advances only under the existing distinct-question contract.
- A confirmed but interrupted review remains safely resumable through the
  canonical pending attempt; an unsubmitted answer is deliberately lost on
  process restart.
- Browser mutation checks remain independent from trusted local voice
  authorization.
- Code fixtures can qualify routing, idempotency, cancellation races, API
  denial, UI projection, and SQLite reconstruction, but cannot establish live
  Qwen teaching quality, physical wake/ASR, audible Pocket/Anna, or hardware
  latency.
- The Stage 31 wake worker remains unchanged. Journal evidence is a recovered
  worker timeout/retry incident; the current read-only health observation is
  healthy. Physical wake/recovery qualification is a separate Owner-approved
  action.

## Qualification

Stage 32 qualification drives synthetic final ASR through the actual voice and
conversation services, fixture local reasoning/Reviewer clients, the test TTS
sink, isolated FastAPI Owner/read paths, and temporary DLP/Career Forge SQLite
stores. It verifies a lesson context event, an uncommitted answer draft, one
explicit confirmed assessment, browser-write denial, correct answer evidence
without premature mastery, interruption races, and reconstruction after
reopening the stores. Frontend tests verify event-derived listening state,
draft projection, and non-submission before confirmation. Physical microphone
qualification is not included.
