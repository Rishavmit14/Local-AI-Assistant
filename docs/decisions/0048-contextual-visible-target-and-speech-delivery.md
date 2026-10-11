# ADR 0048 — Contextual visible-target recovery and complete response accounting

- Status: Candidate; Probe 4 physical acceptance passed; Milestone C remains partial
- Date: 2026-10-09
- Extends: ADR 0044 (goal-bound computer agency), ADR 0046 (direct voice open actions)

## Context

The physical Probe 4 transcript was “Open the second folder in this files
video.” The bounded parser accepts that unchanged wording as an ordinal-folder
intent, but the historical task failed before action because Friday lacked a
trusted current Files location. The previous fixture preflight was older than
the 180-second in-memory interaction-context lifetime, and the durable task
retained an observation count and digest rather than the observed nodes. It is
therefore not possible to prove the active window or visible collection at the
moment of the physical request.

The conversation completion event held the clarification, and Pocket/Anna
produced three response chunks before PipeWire returned successfully. The
voice completion event nevertheless exposed only the initial acknowledgment.
The Owner reported hearing only that acknowledgment; the trace does not prove
the acoustic content at the speaker.

## Decision

Keep the raw ASR transcript unchanged. A visible ordinal intent can be resolved
only from a fresh, unique active Files window and its current visible
collection. If the runner lacks a trusted current location, it reads that
location through Files, dismisses the location field, re-observes the window,
then binds and validates the selected immediate child under owner-controlled
paths. Ambiguous or stale evidence causes clarification without a physical
action. No word substitution or global fuzzy mapping is introduced.

Reuse the existing ordered speech queue and PipeWire player. The completion
event reports all normalized response segments and their roles. Durable task
success or clarification delivery follows the existing playback completion
callback; an acknowledgment alone cannot set `spoken_result` or mark a question
delivered.

## Consequences and limits

Controlled candidate runs opened and exactly verified the second and third
visible folders. Controlled Pocket/Anna + PipeWire runs completed both a
clarification and a terminal failure response after the acknowledgment. Those
checks used no microphone and had no acoustic loopback, so they do not establish
physical listener perception. Probe 4 still requires one physical end-to-end
acceptance attempt at the time of the original entry. The later reloaded
candidate physical Probe 4 passed with exact Files-location verification and
owner-reported final speech. Probe 5 stale-target recovery and Probe 6 active
Stop remain separate and unqualified. This ADR is a candidate recovery record,
not acceptance of Milestone C.
