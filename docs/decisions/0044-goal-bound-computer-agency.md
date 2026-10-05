# ADR 0044: Goal-bound computer agency with trusted legal actions

- Status: Stage 26 candidate; unaccepted until final qualification and publication
- Date: 2026-10-05

## Decision

Stage 26 owner tasks use the persisted local GNOME RemoteDesktop grant without
asking for approval per primitive. The owner goal grants only the bounded action
scope checked by trusted code. Fresh AT-SPI observations supply candidate
controls; the server filters them for active native window, semantic action,
owner object words, dialog context, and consequence policy before any model
selection. Local Qwen may rank only those already legal candidates. One unique
legal candidate follows a deterministic path. The model cannot supply paths,
coordinates, policy, credentials, or postconditions.
If Qwen refuses an ambiguous set, a narrow deterministic fallback chooses
only among distinct low-risk buttons for the same owner object and the same
reveal/open action family. Duplicate names or different objects remain blocked.

A typed controller rechecks the target identity and containing window in a new
observation, claims one action in a private SQLite ledger, marks the actor-start
boundary, executes, re-observes, and verifies an owner-bound result. A short
owner-ordered native plan advances only after each visible effect is verified.
A pre-existing result does not verify a new action. Unknown or consequential
controls fail closed. Browser navigation and no-submit forms remain separate
bounded workflows; arbitrary browser pointer clicks remain blocked without
occlusion proof. Shell execution is not a desktop action.

A process-shared guard covers the entire task transaction. Stop intent is
persisted before waiting for that guard, so a later actor cannot start after a
stop request. Crash recovery never replays an action with an uncertain physical
effect. Exact semantic recovery predicates are bound to the original window;
re-observation may record a uniquely visible result, while the task stays
paused. An explicit Owner Resume may continue a native plan only if the actor
never started or a recovered result remains uniquely visible in a fresh
observation. Earlier verified steps are skipped; action budgets remain
consumed. Older claims without a trusted window binding cannot use positive
result reconciliation.

## Consequences and limits

The path is locally sovereign and uses the existing Qwen model only for
ambiguous legal choices. Four earlier direct model-proposal attempts returned
`blocked`. One new live test over two policy-filtered legal choices also
returned `blocked`; the same-object deterministic fallback completed the real
GTK task with one verified action. Unique-candidate single and two-step paths
also have live GTK/Owner UI evidence. This does not establish arbitrary natural-language planning,
arbitrary coordinate safety, or authorization for consequential UI actions.
Real reboot/login restoration, full regressions, secret audit, and Stage 26
publication remain acceptance gates.
