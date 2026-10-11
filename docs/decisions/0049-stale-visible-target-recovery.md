# ADR 0049 — Reject and safely re-ground stale visible targets

- Status: Candidate; Probe 5 physical stale-target journey passed; Milestone C remains PARTIAL
- Date: 2026-10-09
- Extends: ADR 0044 (goal-bound computer agency), ADR 0048 (visible-folder actions)

## Context

A semantic target can change after the owner intent is resolved and before the
runner dispatches its action. Reusing the prior target identity or coordinates
can act on the wrong item. The desktop controller already rejects expired or
changed action evidence and preserves uncertain effects for explicit recovery,
but the visible-collection route needed an audited way to determine whether a
changed collection still contains the same intended referent.

Probe 4 also left a reproduced voice lifecycle defect: when trusted barge-in
stopped playback while model generation was streaming, the completed owner
utterance could be dropped if the response stream ended first. The wake
orchestrator could then try to re-arm a listener while the runtime was already
listening.

## Decision

Bind each visible collection target to its source observation, active
application/window, semantic identity, containing collection identity and
ordered collection digest. Before dispatch, take a fresh observation and
rebuild the collection. Persist stale rejection as a separate action record
with the new observation; never rewrite the rejected action as verified or
increment the action count for it.

A fresh target may be rebound only when the active application/window,
collection identity, semantic role and label, and requested ordinal still
identify the same item. A trailing addition can therefore preserve the second
folder if it remains second. If a new item takes that ordinal, or the window,
application, focus, geometry, or target identity no longer matches, stop and
clarify. Recovery is bounded to one stale rejection; no old coordinates or
uncertain physical action are replayed. The existing controller remains the
pre-dispatch authority for all desktop actions; visible-collection rebinding
is a semantic helper that is not specific to Files labels or folder names.

For a deterministic physical qualification, an optional owner-only
`FRIDAY_AGENCY_TEST_GATE_DIR` may name a 0700 directory containing a 0600
fixture configuration. The one-shot gate blocks after a trusted binding,
checks that the external harness added exactly the configured owner-controlled
folder while preserving the bound folder, and then releases the normal fresh
observation/re-grounding path. It fails closed on mismatch or timeout and
cannot dispatch or skip a trusted action. With the variable absent, it is
inactive.

On confirmed trusted barge-in, signal cancellation to the response stream from
the monitor boundary before playback-worker teardown. Preserve the completed
interruption utterance for the normal transcription and wake-session path.

## Consequences and limits

Deterministic tests cover safe trailing-addition recovery, changed-ordinal and
wrong-window refusal, generic browser result-collection rebinding, no replay of
uncertain actions, and midstream barge-in re-arming. An earlier physical request window received no wake-accepted event, voice task,
or target-bound checkpoint. It made no folder change and released no action;
that attempt did not exercise the microphone path or recovery contract.

A later coordinated physical Probe 5 passed. The actual service process loaded
the candidate runner and gate; the gate added Zephyr after Birch was bound at
ordinal two. The prior action was persisted stale without dispatch. Friday took
a fresh observation, re-grounded Birch, opened it, verified the exact Files
location, and durably completed the task with a spoken result. The Owner
confirmed success. The watcher mislabeled playback because final speech event
21 preceded task completion event 23; the completed speech event and Owner
confirmation resolve the false negative. Cleanup restored the fixture, removed
the temporary drop-in, unloaded the gate, and returned Friday to healthy
listening. Private correlation and cleanup evidence are under the owner-only
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-final-20261010T090023Z-c9e2/preflight-rearm-1/` directory.

Probe 5 is physically passed. This candidate does not qualify Probe 6 active
Stop or Milestone C as a whole; those acceptance gates remain outstanding.
