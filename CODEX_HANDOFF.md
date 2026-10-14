# Stage 28 Astra UI publication — 2026-10-15

## Accepted scope and current state

- Candidate worktree: `/home/kumar-rishav/.codex/worktrees/friday-stage28-final-visual/Local-AI-Assistant-terra-integration`.
- Owning branch: `stage-28/final-product-visual-acceptance`, based on the published `a550266190befb4795c0572b9062e7d5801e2fce` checkpoint.
- The Owner approved the exact Astra UI on 2026-10-14 and authorized qualification, publication to this Stage 28 branch and `main`, and activation at `http://127.0.0.1:5193`.
- The final accepted branch tip is the Stage 28 publication recovery checkpoint. The live main worktree is a clean worktree at `~/.codex/worktrees/friday-stage28-live-main/Local-AI-Assistant-terra-integration`; the original dirty `/AI/projects/Local-AI-Assistant-terra-integration` main checkout was preserved.
- The `friday-ui.service` user unit serves the built UI on loopback at port 5193. It uses `NoNewPrivileges=yes` and `UMask=0077`. This host's user systemd manager rejects mount, UTS, and capability namespace sandbox setup, so unsupported sandbox directives are omitted. The service continues to use existing API authentication, CSRF, Owner-task authorization, and restore checks.
- The rollback unit and original GCA checkout remain intact. Rollback instructions are in `docs/operations/friday-ui.md`.

## Qualification evidence

- All 16 registered routes passed at five viewports (1440×900, 1280×800, 768×1024, 390×844, and 320×740): 80 route/viewport checks, with no horizontal overflow, clipped focusable controls/headings, or mobile-route mismatch.
- Keyboard navigation, modal focus containment/restoration, accessible labels, tabs, and reduced-motion behavior have regression coverage. The host browser reports native reduced motion as false and cannot emulate it, so no reduced-mode screenshot is claimed.
- Frontend: 168 tests across 35 files, four Node Owner-bridge/local-server checks, ESLint, TypeScript, and production build passed. The existing Vite large-chunk advisory remains (~1.29 MB JavaScript).
- Repository verifier passed with Python 3.11: 1,839 passed and 6 skipped; `pip check` passed. The initial Python 3.14 fallback had environment-specific subprocess and Bubblewrap failures; the corrected interpreter was the repository's existing `.venv`.
- `systemd-analyze --user verify` passed for the unit templates with only an unrelated existing `spice-vdagent.service` unknown-key warning.
- Live qualification on port 5193 returned HTTP 200 for `/` and `/health`, showed the real Friday UI, and completed a local Qwen conversation with `READY` after confirming the shared session was inactive and empty. No microphone, voice, computer action, owner restore, or learner-state write was exercised. Friday API, Qwen, Pocket/Anna, voice, and computer-control processes were not restarted.

## Product status and protected state

- Career Forge Roadmap rows 60 and 61 remain **PARTIAL**. The approved and live Stage 28 UI does not close broader Career Forge or whole-product qualification. Populated owner-state visuals and native reduced-motion browser capture remain limitations.
- Protected `/AI/projects/Local-AI-Assistant`, the original GCA rollback worktree, the earlier `experiment/final-neetcode-ui` worktree, owner credentials/data, Qwen weights, and unrelated dirty local-main `ROADMAP.md` were preserved. No secret or credential value is committed.
- No known blocker remains for the authorized Stage 28 UI publication. The next canonical capability is the active `ROADMAP.md` dependency after this UI publication; reconstruct it from the roadmap and architecture rather than this historical conversation.

## Recovery and validation

At publication, verify that `stage-28/final-product-visual-acceptance` and
`main` resolve to the same remote commit, and that the clean live-main worktree
matches that commit. Check `systemctl --user is-active friday-ui.service` and
`http://127.0.0.1:5193/health`. To roll back only the UI, disable and stop
`friday-ui.service`, then enable and start `friday-ui-rollback.service`; do not
restart Friday API, Qwen, Pocket/Anna, voice, or computer services.
