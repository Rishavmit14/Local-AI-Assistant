# Validation intelligence

Stage 5 adds a quality gate without adding execution authority. Its enforced order is:

`approved plan -> scoped execution -> structural checks -> targeted tests -> bounded repair -> full required validation -> deterministic review -> security review -> model review -> final decision -> commit or rollback`

`ValidationPlan` binds every check to the task, exact plan hash, repository, and starting commit. Steps are typed as required, recommended, or optional. A missing or skipped required tool is a failure, never a presumed pass. Repository configuration and affected-file evidence select validators and targeted tests; selection is ranked and explicitly not claimed complete.

Targeted failures may enter the bounded repair engine. Repair prompts contain the original request, exact failure evidence, approved plan, and bounded current diff. Candidate patches pass the Stage 4 pre-apply and post-apply scope checks. A repeated failure, infrastructure failure, exhausted attempt budget, risk increase, or scope increase terminates repair. No validator, reviewer, or model can widen the approved plan.

Final review runs deterministic checks first, including scope, unrelated changes, test weakening, public API deletion, placeholders, security patterns, dependency hazards, and conservative performance/concurrency signals. The local model receives only bounded, redacted plan/diff/findings context. Its findings are additive and cannot remove deterministic findings.

The final decision is one of `PASS`, `PASS_WITH_WARNINGS`, `REPAIR_REQUIRED`, `REAPPROVAL_REQUIRED`, `BLOCKED`, or `FAILED`. A required validation failure, hard scope failure, or blocking deterministic finding cannot be overridden by model output.

The deterministic classifier treats Python `NameError` traceback evidence as a
runtime defect that may enter bounded repair. Such repairs remain subject to
the exact approved patch scope, risk checks, attempt limit, and targeted-test
rerun; unknown failures remain non-repairable.

## Limitations

Static review is heuristic, not formal verification or a vulnerability audit. Targeted-test inference can be incomplete. Flaky classification requires repeated no-change rerun evidence and does not dismiss the original failure. External security and coverage tools run only when already installed and configured.

Validators execute through the Stage 4 parsed command policy. Stage 5 detects repository mutations and restores exact tracked, staged, untracked, mode, and symlink state, but it is not an operating-system sandbox: untrusted test code can still attempt external side effects. Filesystem/container isolation remains explicitly scheduled for Stage 8, so repositories and validation commands must be trusted until that boundary exists.

### Candidate failure disposition audit (Stage 22)

Syntax, import, missing-name, TypeError, AttributeError and assertion defects
may enter the existing bounded, exact-scope repair. Import repair never installs
dependencies automatically. Scope/security rejection is policy-blocked;
environment/transport/infrastructure failure requires infrastructure recovery;
timeout and unknown subprocess exits fail safely. Malformed model/schema output
is eligible only for the existing bounded protocol correction, not a code
repair. Repeated failure or exhausted budget still terminates repair.
Policy and infrastructure diagnostics take precedence over incidental traceback
text. Repair uses current candidate source, strict JSON schema and finish-reason
checks; malformed text is never made executable through JSON coercion.
