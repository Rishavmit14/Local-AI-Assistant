# Friday handoff — Stage 30 deployed and verified

Updated 2026-10-16 after owner-approved Stage 30 release and live deployment.
Production serves immutable release
`2c200bf798e195f2fff4908b147304d46a49d795` (tree
`de49e9a55576dafe2bbfe4c3e46133be1789498a`). Stage 30 is accepted and
recoverable. The handoff/roadmap/history/operations updates are published as a
documentation-only follow-up on the same Stage 30 branch; runtime code and the
immutable release are unchanged. Resolve the Git tip with `git rev-parse
HEAD`; the deployed runtime SHA remains the exact value above.

## Repository and release state

- Stage worktree:
  `/home/kumar-rishav/.codex/worktrees/friday-stage30-connected-journey/Local-AI-Assistant-terra-integration`
- Owning branch: `stage-30/career-forge-connected-journey`.
- Main integration worktree:
  `/home/kumar-rishav/.codex/worktrees/friday-stage28-live-main/Local-AI-Assistant-terra-integration`.
- The Stage 30 source commit was fast-forwarded from Stage 29 without force;
  `origin/main` and `origin/stage-30/career-forge-connected-journey` were
  verified at `2c200bf798e195f2fff4908b147304d46a49d795` before deployment.
  Both refs now point to the same documentation-only follow-up commit, which
  preserves the deployed release source SHA and changes no runtime code.
- Runtime pointer:
  `/home/kumar-rishav/.local/share/friday/api/current` resolves to
  `/home/kumar-rishav/.local/share/friday/api/releases/2c200bf798e195f2fff4908b147304d46a49d795`.
- Release environment:
  `/home/kumar-rishav/.local/share/friday/api/environments/2c200bf798e195f2fff4908b147304d46a49d795`.
- Stage 30 deployment evidence and restricted backups:
  `/home/kumar-rishav/.local/share/friday/api/maintenance/stage30-2c200bf798e195f2fff4908b147304d46a49d795/`.
- Protected Terra and GCA worktrees were not modified. Do not reset, clean,
  or stash them.

## Deployment and validation

- API and UI are active on the immutable Stage 30 release. Their systemd
  working directories, process directories, API environment, current pointer,
  and source root resolve to the exact release. Health and same-origin proxy
  checks return HTTP 200.
- Projects is schema v3; Learning Paths remains v2. All 15 production SQLite
  databases pass integrity checks, and all post-deployment table counts match
  the verified post-API-stop backup. No production project or learner records
  were created.
- Owner-only read, mutation, and trusted-session restoration without owner
  proof return HTTP 401. The isolated Stage 30 browser/API run covers the
  authenticated Owner/CSRF flow. All 13 live frontend assets match the release
  manifest; Projects and Career Forge same-origin routes work.
- Voice is running with capture, stream, and wake path armed, no active turn,
  and Pocket/Anna selected. The runtime capability endpoint reports healthy
  voice, computer agency, and perception. Qwen's read-only model listing
  passed; no inference or Qwen/vision restart occurred. No GPU or swap change
  occurred.
- TaskHistory has zero tasks or planning/execution claims. The existing active
  Career Forge mission, its assistance row, and saved Practice Lab draft were
  preserved. The 12 historical `in_doubt` computer actions remain untouched.
- Qualification: Python repository verifier **1,868 passed, 6 skipped**;
  frontend **184 tests across 37 files**, four Node checks, ESLint, TypeScript,
  and production build passed. Deployment evidence additionally records exact
  API/UI health, asset hashes, Owner rejection, capability health, and all
  database checks. The Vite main-bundle size advisory (about 1.29 MB vs 500 kB)
  remains disclosed.
- A first UI-stop wrapper misread systemd's normal inactive exit code after
  stopping only UI. API remained healthy; UI recovered before the corrected
  cutover. That attempt changed neither the release pointer nor databases.
  The incident and recovery are recorded in HISTORY and the operations plan.

## Active scope and next path

- Stage 30's bounded FraudShield source-artifact journey is deployed. It does
  not qualify the full Career Forge ecosystem; ROADMAP rows 60 and 61 remain
  PARTIAL. The cutover's point-in-time active-work admission limitation and
  rollback procedure remain documented in
  `docs/operations/stage30-release-plan.md`.
- No Stage 31 work was started in this release task. The next roadmap path is
  the broader Senior ML/AI Engineer learning journey; start it only on its
  owning Stage 31 branch and preserve all existing Owner, isolation, rollback,
  audit, and local-sovereignty controls.
- No deployment action remains. The exact next roadmap path is the Stage 31
  Senior ML/AI Engineer learning journey on its own Stage 31 branch; it was not
  started in this Stage 30 release task. Do not move the production pointer
  away from release SHA `2c200bf798e195f2fff4908b147304d46a49d795`.
