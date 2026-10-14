# Current Friday handoff — Stage 28 Astra UI

Updated 2026-10-15. Reconstruct from this file, the canonical docs, and Git;
chat history is not required.

## Recovery state

- Stage candidate: `/home/kumar-rishav/.codex/worktrees/friday-stage28-final-visual/Local-AI-Assistant-terra-integration`, branch `stage-28/final-product-visual-acceptance`.
- Live UI worktree: `/home/kumar-rishav/.codex/worktrees/friday-stage28-live-main/Local-AI-Assistant-terra-integration`, branch `main`.
- Prior Stage 28 documentation checkpoint: `b0f48cd150277981a920bb28b3c397979d0ee548`; Stage 28 branch and `main` were pushed and direct `git ls-remote` plus fetch verified both at this exact SHA. The current handoff adds the owner-facing Learn/Projects route observation and remains documentation-only relative to implementation/dependency-audit checkpoint `018dc4bb7b609d23111060b0112e630cfa852b3d`.
- The enabled `friday-ui.service` is active on loopback port 5193. At the final service check, `/` and `/health` both returned HTTP 200; UI PID was 156835 and the existing Friday API PID was 7350. The UI process has `NoNewPrivileges=1`. The browser showed Home with Friday ready and the authorized local Qwen smoke turn returned `READY`.
- Friday API, Qwen, Pocket/Anna, voice, and computer-control processes were not restarted. No microphone, computer action, restore, or learner-state write was exercised.
- Original checkout `/AI/projects/Local-AI-Assistant-terra-integration` remains attached to `recovery/local-main-before-stage28-20261015` at `47ae92bba1c3b50d9dd6f2264d95b6cfaf275e75`; its pre-existing dirty `ROADMAP.md` is preserved (SHA-256 `c804f92177ddbe033d81904aee3d59a6b5af748bca5d655ee6bb632c3bede897`). Private recovery patches and snapshots are under `/home/kumar-rishav/.local/state/friday-stage28-publication/`. Do not reset or replace that checkout.

## Qualification and limitations

- All 16 UI routes passed at five viewport sizes (80 route/viewport checks). Frontend: 168 tests across 35 files, four Node Owner-bridge/local-server checks, lint, TypeScript, and production build passed. Full and production npm audits report zero vulnerabilities.
- Repository verifier passed on Python 3.11: 1,839 passed, 6 skipped; `pip check` passed. `systemd-analyze --user verify` passed with an unrelated installed `spice-vdagent.service` warning.
- Existing Vite large-chunk advisory remains (~1.29 MB). Host browser cannot emulate native reduced motion, so no reduced-motion screenshot is claimed. Populated owner-state visuals and broader integrated Career Forge flows remain open.
- Career Forge roadmap rows 60 and 61 remain **PARTIAL**; this publication does not qualify the full product. Friday API PID 7350 runs from `/home/kumar-rishav/.codex/worktrees/friday-general-computer-agency/Local-AI-Assistant-terra-integration`, branch `stabilization/general-computer-agency`, HEAD `09842e7eefcdda6df34d5f4163078fb6cca29e06`, with extensive pre-existing uncommitted changes. Preserve this active runtime worktree; do not clean, reset, or edit it. Its OpenAPI listed 136 paths; read-only GETs to learning-path, Projects, and watch list endpoints returned HTTP 200. The earlier 404 observation was not reproduced, so no current missing route is confirmed.
- Read-only browser review found the current Learn mission and a valid 0/16 skill roadmap, but no saved dynamic learning paths or assigned projects. Projects lists four canonical project pathways. Expanding FraudShield and selecting “Explore the learning path” navigated to generic Learn; it did not carry project identity/focus or select/create a project-specific learning path. The path-creation form was only expanded and left empty; no learner state was written. The static frontend/API path comparison found no confirmed missing route after accounting for query suffixes and the allowlisted Practice Lab action parameter.
- The rollback unit and original GCA checkout remain available. See `docs/operations/friday-ui.md`; rollback affects only the UI service and must not restart Friday API, Qwen, Pocket/Anna, voice, or computer services.

## Active dependency

Continue Row 60/61 Career Forge integration. The first concrete slice is the
project-template-to-learning handoff: preserve selected project identity and
focus when opening Learn, and offer an owner-controlled, prefilled path goal
without creating a path, project, evidence, or mastery state automatically.
Confirm the intended behavior against the product baseline before changing
code; retain the current empty state and owner choice. Keep this Stage 28
worktree and the dirty live GCA runtime worktree unchanged. Use a fresh
roadmap-stage branch/worktree for implementation and qualification.
