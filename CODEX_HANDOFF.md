# Friday current recovery handoff

Repository: `Local-AI-Assistant`; integration worktree:
`/AI/projects/Local-AI-Assistant-terra-integration`.

## Accepted state — Phase 19 / row 59

Phase 19 qualifies **bounded Local Intelligence Sovereignty**. Capability
commit `a7010a3213e3938929813f0a4feec6e8d931c8a0` implements the candidate
Owner Sovereign boundary; qualification commit
`794f60508d720ec8b0ce61040815821d626e62b6` records the bounded row-59
acceptance. At the handoff update, branch `integration/astra-friday`, local
`main`, fetched `origin/integration/astra-friday`, and fetched `origin/main`
all pointed to the qualification commit; the handoff-only update is its
descendant and must be pushed/fetch-verified to both remote refs.

All native and integrated Phase 19 checks passed. Full repository verification
passed (1,099 Python tests, package/CLI/artifact checks, and `pip check`); full
frontend validation passed (105 tests, ESLint, TypeScript, and production
build); changed Python files passed targeted Ruff; `git diff --check` and
installed systemd unit verification passed. Global Ruff reports 36 diagnostics
across 21 unchanged files; no global mass-fix was applied.

The exact scope and limits are in
`docs/qualification/owner-sovereign-mode.md`, ADR 0033, and row 59 of
`docs/qualification/PRODUCT_INTEGRATION_MATRIX.md`. In brief: privileged file,
transient-systemd, broker-restart, and private-network probes passed with sudo
timestamps invalidated; the enrolled credential remained available after
broker restart; the service ran under owner UID/GID in a distinct network
namespace and host user namespace; external and host-loopback probes were
denied. Practice Lab, same-UID process, API/client, and model-facing boundaries
have deterministic negative coverage. A real local-Qwen E2E passed synthetic
Research, Memory-backed Conversation, Career Forge cognition/evaluation,
CodeRAG/planning, Reviewer/Security, and local recovery after optional external
adapter failure. The broker policy trusted only the qualification probe;
production Friday does not use it, and production administrative UI/API
integration remains unqualified. No owner private documents or Career Forge
state were used.
This does not qualify all Friday capabilities, first-install offline behavior,
browser-process network isolation, or confidentiality from trusted root.

## Protected runtime invariants

- Production checkout `/AI/projects/Local-AI-Assistant` is protected; retain
  its pre-existing Pocket/Anna owner changes exactly.
- Production Friday `127.0.0.1:8765` and local Qwen `127.0.0.1:8080` must remain
  running and unmodified.
- Owner Career Forge state and private documents remain untouched.
- No host networking, firewall, route, DNS, or NetworkManager changes were made.
- The candidate policy trusts only
  `friday-owner-sovereign-probe.service` (owner UID/GID 1000). Do not add the
  production Friday unit to this qualification policy.
- The candidate probe was stopped after evidence capture; the persistent
  system broker/socket and encrypted credential are the Owner Sovereign runtime
  itself, not disposable test state.

## Next dependency and stop boundary

Do not start matrix row 60 implementation. After row 59 is committed and
remotely recoverable, stop at the requested boundary. The next product-design
step is to reread `FRIDAY_PRODUCT_BRAINSTORM.md` and write the final
owner-facing product/UI and Dynamic Learning Paths specification before any
row-60 implementation.

Fresh sessions must read `AGENTS.md`, this handoff, `ROADMAP.md`,
`ARCHITECTURE.md`, `HISTORY.md`, `FRIDAY_PRODUCT_BASELINE.md`, the matrix, ADR
0014, ADR 0033, and the Phase 19 qualification report. Repository/runtime truth
overrides older session snapshots.
