# Validation and review operations

Build and inspect a validation plan:

```bash
local-ai-validate build-plan PLAN.json --output VALIDATION.json
local-ai-validate show-plan VALIDATION.json
```

Run the two phases explicitly:

```bash
local-ai-validate run-targeted PLAN.json VALIDATION.json --output targeted.json
local-ai-validate run-required PLAN.json VALIDATION.json --output final.json
```

Other commands include `classify-failure`, `review-diff`, `security-scan`, `show-findings`, and `export-report`. Artifacts use schema-versioned JSON and atomic replacement. Cache entries are successes only and are keyed by repository, starting commit, current diff, exact command, and validation configuration.

The coding agent invokes the same phases automatically in tool-loop apply mode. Repairs use the approved Stage 4 tool context, so approval tokens, repository identity, HEAD, file/symbol limits, and pre/post diff enforcement remain active. Final commit is possible only after a passing final decision; otherwise the existing Git transaction rolls back.

Use `--generate-tests` with the complete tool-loop apply safety bundle to request a bounded test mutation before implementation. Add `--tdd` to require that test to produce an assertion/regression failure before implementation begins. Import, environment, timeout, or infrastructure failures are not accepted as a TDD RED phase. The generated patch is applied through the same Stage 4 scope gate and remains in the final reviewed Git diff.

No command installs tools. An unavailable required validator fails conservatively. Outputs are bounded and credential-like values are redacted before persistence or model review.
