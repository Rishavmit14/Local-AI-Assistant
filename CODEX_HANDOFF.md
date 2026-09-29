# Friday current recovery handoff

Repository: `/AI/projects/Local-AI-Assistant-terra-integration` on
`integration/astra-friday`. The accepted pre-UX Phase 19 recovery HEAD was
`aae600a823e03cdb4d0e24c9d20cee71bd5857ff`. UX-60A is the current
capability checkpoint; recover its exact commit from the common verified
`HEAD`, `origin/integration/astra-friday` and `origin/main` refs. The final
publication verification and actual test counts are in the UX-60A History entry
and Git history. The accepted worktree is clean after publication.

## UX-60A recovery

The interrupted earlier UX session had no staged files or new commits. Eleven
tracked files and four untracked files were preserved in external rescue
snapshot `/tmp/friday-ux60a-pre-redirection-XvBcif` (mode 0700), including
unstaged/staged patches, untracked tar, status, HEAD, commit list and checksums.
It contains no known secret material. KEEP: compatible product routes,
canonical workspace wording, Settings disclosure and History simplification.
MODIFY: the partial shell's generic Home and blue engineering-heavy styling;
Home now mounts the exact Astra Ultra brain alongside the canonical Friday
Conversation, and Learn uses the NeetCode-led dark, scannable layout. REVERT
SELECTIVELY: none was necessary. `NeuralPresence.tsx` and its supporting
`Vision.css` were unchanged from `aae600a`; no brain component restore was
required. `docs/product/NEETCODE_UX_REFERENCE.md` records observed public
reference pages and originality boundaries.

The persistent primary navigation is Home, Learn, Projects, Knowledge,
Automate and History, with Notifications and Settings. Existing hash routes
remain compatible. Learn shows the existing Career Forge Overview, Roadmap,
Practice, Interview and Progress; Projects, Knowledge, Automate, History,
Memory, Perception and Developer / Diagnostics keep their canonical service
boundaries. Home and `#conversation` share `FridayRuntimeStore`. Ask Friday
returns to Home with a route back to the prior workspace; no automatic page
context is claimed. No Dynamic Learning Paths backend or owner learner-state
change was made. Matrix row 60 stays PARTIAL. Next recommended dependency is
DLP-1, deliberately not started in this rescue.

## Validation and limits

Native browser inspection covered current public NeetCode Home, Roadmap topic
panel, Practice, Courses and a public lesson; candidate Friday Home and brain
states, Conversation, Learn Overview and Roadmap, Practice availability,
Projects, Knowledge, Automate, History, Notifications, Settings,
Developer / Diagnostics, command palette and a smaller window. The candidate
presentation API on loopback port 5192 uses disposable
`/tmp/friday-ux60a-state`; candidate Vite on 5193 proxies it. Production
Friday/Qwen were not restarted or changed. The production API remains older
than this integration candidate, so UX-60A browser qualification uses the
isolated candidate rather than treating older-production 404s as product data.
Current Career Forge Practice has no active mission in the candidate, so its
unavailable state is truthful; no owner mission was started for design review.

Final gates passed: 107 frontend tests, ESLint, TypeScript, production build,
1,099 Python tests, repository package/CLI/artifact checks, `pip check`,
targeted Ruff, and `git diff --check`. Fetched remote-ref and clean-worktree
verification complete publication. One MCP subprocess test
had a 15-second timeout despite an approximately 11-second measured cold CLI
startup. Its timeout is 45 seconds while the EOF/protocol assertions remain.
A full-suite source-fingerprint assertion also failed once because source files
were edited during that run; the final stable-source verification passed.

## Protected production and next step

Protected production checkout `/AI/projects/Local-AI-Assistant` remains on
`stage-22/product-integration` at
`e43896623978e86b7bae6502b380462b455626be` with its pre-existing
Pocket/Anna voice changes. Preserve that checkout. Production Friday
`127.0.0.1:8765` and Qwen `127.0.0.1:8080` remain owner runtime services;
no restart was required for UX-60A. Owner Career Forge and private documents
were not mutated. Phase 19 Owner Sovereign evidence remains candidate-bounded;
production privileged integration is not qualified.

Stop after publishing and fetch-verifying UX-60A. DLP-1 and row 61 are outside
this rescue. Fresh sessions must reconstruct current truth from Git, this
handoff, product contract, roadmap, architecture, history, matrix and host
runtime rather than the old UX transcript.
