# ADR 0040 — Reviewed task promotion and Project assessment

- Status: Accepted for the Stage 22 local Project qualification
- Date: 2026-10-03
- Authority: owner-authorized Friday Project lifecycle

## Decision

Task execution success is not permission to publish code or award learner
evidence. Friday records a final task commit only after exact-plan promotion
verifies the latest completed attempt, immutable execution artifact and diff,
required final test steps, a nonblocking local Reviewer result, the isolated
branch and starting commit, and a clean canonical repository at that commit.
Promotion records the resulting commit in TaskHistory with the attempt identity
and audit event. Project submission derives changed file paths from that exact
commit, including files created by the task. The browser cannot supply a
different commit or arbitrary artifact paths as reviewed task output.

The Project's independent learning assessment uses the same accepted local Qwen
model in its Reviewer role. The trusted acceptance contract is normalized into
explicit inclusive intervals and boundary examples before assessment. Model
output must contain a complete bounded evidence line and final verdict;
truncated, malformed or contradictory output is uncertain and awards no
evidence. A correct verdict writes a single provenance-linked Career Forge
record with path, milestone, task, commit, artifact and review-attempt identity.
Project completion does not promote mastery; Career Forge retains its own
independent-application and retention rules.

## Qualification and limits

The FraudShield task passed its approved full `python -m unittest discover -v`
suite inside denied-network isolation before promotion. The browser submitted
three committed artifacts, and the local Reviewer accepted a complete
explanation after earlier rejected attempts remained without evidence. Reload
and candidate API restart reconstructed the Project and Learn state. The task
commit remains in its isolated disposable repository; this ADR does not
authorize publication of learner code to GitHub. Stage 22 repository
publication is the separate engineering checkpoint governed by `AGENTS.md`.
