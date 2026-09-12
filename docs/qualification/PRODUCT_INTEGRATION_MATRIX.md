# Friday Product Integration Matrix

**Audit date:** 2026-09-12
**Repository baseline:** Stage 21 accepted at `3770151bbf146ff580b8cafa0b4f73a0865c55c5`
**Scope:** owner-facing product reality, not a historical-stage scorecard.
**Authority:** `FRIDAY_PRODUCT_BASELINE.md` §§1, 21–26; architecture and ADRs
remain authority for safety and accepted boundaries.

## Method and status discipline

Each row traces the actual available path: owner -> voice/text/UI ->
presentation/conversation -> policy -> capability -> persistence -> visible
outcome. `B` below names code/API evidence; `Conv` and `UI` state whether that
route is actually connected today. `—` means no owner route, not merely an
uninspected route. Status uses only the baseline vocabulary. A backend primitive,
endpoint, database, CLI, unit test, stage label, or rendered card is never by
itself usability evidence.

Current deterministic evidence inspected: `interface/conversation.py`,
`interface/voice_conversation.py`, `voice/wake_orchestrator.py`,
`interface/wake_bootstrap.py`, `interface/api.py`, `interface/cli.py`, the
frontend components/runtime client, subsystem services, their focused tests, and
the relevant architecture/ADRs. Live evidence at audit time: the user service was
`active/running` on localhost `:8765`; `/health` was OK; runtime state was
`completed`; wake capture/workers were alive. Voice health retained a historical
`WakeRuntimeError` timeout with recovery count 86, so liveness is not a clean
voice-product qualification.

**Abbreviations:** `API` = loopback presentation endpoint; `CF` = Career Forge;
`TS` = task history; `E2E` = real owner-facing qualification required; `N/A` =
not applicable because the capability is absent/deferred.

## Capability matrix

| Capability | Backend Evidence | Conversation Route | UI Route | Persistence | Permission / Authority Boundary | Owner Invocation Path | Existing Real E2E Evidence | Current Product Status | Exact Gap | Recommended Integration / Remediation | Dependencies | Qualification Required |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. Wake activation | strict matcher, managed capture and worker health | Yes: strict `Hey Friday` enters a session | live runtime/session state | telemetry/journal | wake only, fail-closed | physical wake | Slice 1 real wake/stop run; capture healthy afterward | QUALIFIED | longer stability remains a separate product concern | preserve as session entry | voice lifecycle | clean live wake/recovery smoke |
| 2. Continuous conversational session | orchestrator holds wake pause across fresh follow-up captures | Yes: wake once, then bounded follow-ups | truthful session-active footer/state | bounded in-process session record | interaction lease; one microphone reader | wake once then speak naturally | physical multi-turn follow-up and pause succeeded | USABLE | full baseline ten-turn qualification is still pending | retain bounded session controller | 1, 6 | baseline E2E-001 |
| 3. Natural multi-turn conversation | session turns are injected before model response with source-priority policy | Yes: owner/Friday prior turns | shared text/voice state where composed | max 16 turns / 12k chars | no mutation authority | natural follow-up/correction | owner requalification passed current-discussion recall and source distinction | USABLE | full ten-turn pause/correction flow remains pending | retain bounded context and qualify baseline | 2, 6 | 10-turn pause/correction flow |
| 4. Barge-in/interruption | AEC/Silero/Piper path | Yes during playback | event signal | bounded telemetry | trusted speech only | interrupt spoken response | accepted physical Stage 12 | QUALIFIED | only within one-shot turn; not session continuity | preserve while session controller changes | 2 | regression + live barge-in |
| 5. Explicit stop | exact stop classifier | Yes | runtime signal | events/telemetry | exact commands only | `stop` / `Friday stop` | accepted physical Stage 12D | QUALIFIED | none for current bounded semantics | preserve | 2 | affected voice regression |
| 6. Active-session working context | typed session controller and source-priority prompt policy | prior turns are primary evidence for current-discussion references | state/footer reflects actual active state | max 16 turns / 12k chars, cleared on close | model cannot mutate session into durable memory | normal follow-up | physical owner requalification passed Career Forge discussion recall and post-close cleanup | USABLE | explicit text-session close policy is still narrow | maintain bounds/lifecycle; qualify baseline | 2, 3 | E2E-001/002 |
| 7. Persistent memory | `FridayMemoryService`, SQLite, lexical/local embeddings | narrow explicit owner remember/recall/forget router path | raw recall/remember API only | SQLite | typed owner intent; model read-only | natural explicit owner phrase or API/CLI | real text save → restart → recall → governed deletion passed | USABLE | only strict explicit form; physical-memory product proof remains | retain explicit provenance boundary | 6 | restart memory E2E |
| 8. Memory recall through normal conversation | `memory.search(prompt, limit=5)` plus separate active context | retrieval is connected and labelled untrusted | composer uses same endpoint | SQLite | retrieved text cannot grant instructions or mutate memory | ask related prompt | live explicit record was recalled through local conversation | USABLE | query-match recall; no natural remembering/capture proof | explicit memory UX with provenance | 3, 7 | E2E-002/003 |
| 9. Capability self-awareness | typed registry grounded into conversation | Yes: authoritative product-state answer | read-only capability endpoint/session state | composition state only | descriptive only; grants zero execution authority | ask Friday | live Career Forge answer reported integrated route and Practice Lab limitation | USABLE | capability invocation/routing is not yet general | capability-aware router, preserving policy | 10, 26 | E2E-004/011 |
| 10. Runtime capability discovery/registry | `FridayCapabilityRegistry` at composition boundary | capability context passed to model | `GET /api/v1/capabilities` | in-process live projection | descriptive health/config/permission only | API or ask Friday | live API and grounded conversation verified | INTEGRATED | no owner-facing capability workspace | route existing capabilities through policy | 9 | registry consistency/restart test |
| 11. Application launch | `DesktopControlService.LAUNCH_APP` | No | pending-action console only | desktop SQLite audit | exact allowlist + proposal/approval/one-time execution | API-created proposal, then UI review | Stage 16 controlled evidence | IMPLEMENTED | no natural conversation request; friction | capability routing + risk policy | 9, 10 | launch allowed app flow |
| 12. Browser launch | generic app launch only | No | No proposal creator | audit SQLite | exact allowlist | manual API if configured | no owner flow | PARTIAL | browser not modeled/naturally reachable | explicit browser action capability | 11 | E2E-005 |
| 13. Website navigation | `OPEN_URI` allowlisted origins | No | No | audit SQLite | HTTPS origin allowlist + approval | manual API if configured | backend tests only | IMPLEMENTED | no natural `Open YouTube` path | semantic low-risk URI route | 11, 12 | E2E-006 |
| 14. Folder opening | no folder action (`OPEN_FILE` requires file) | No | No | — | — | none | none | ABSENT | folders unsupported | safe allowlisted folder open lifecycle | 11 | E2E-007 |
| 15. File opening | `OPEN_FILE` allowed roots | No | No proposal creator | audit SQLite | existing file + root allowlist + approval | manual API | backend tests only | IMPLEMENTED | disconnected and approval-heavy | conversation/UI route with truthful policy | 11 | E2E-007 |
| 16. File creation/editing | coding executor can mutate isolated repos | No direct owner route | objective plans only; no execution control | TS/checkpoints/audit | exact approval/isolation/validation/Git | guarded engineering objective, not files | Stage 17 controlled task | IMPLEMENTED | no desktop/file authoring product flow | separate reversible file workflow; preserve executor gates | 48, 55 | E2E-008 |
| 17. File deletion/recovery/undo | rollback in isolated executor; no desktop delete | No | No | TS/checkpoints | high-risk gates | none | no product E2E | PARTIAL | no owner file delete/undo route | recoverable sandboxed file action design | 16, 55 | E2E-008/015 |
| 18. Keyboard/mouse/UI action | exact AT-SPI targets only | No | No proposal creator | desktop audit | allowlisted semantic action + approval | manual API | Stage 16 test evidence | IMPLEMENTED | no arbitrary desktop agency/shared context | expand only evidence-backed semantic controls | 20, 23 | controlled action E2E |
| 19. Package installation | no package action | No | No | — | — | none | none | ABSENT | baseline command unsupported | scoped package workflow with risk policy | 16, 55 | install + rollback/audit E2E |
| 20. Screen perception | capture/OCR/UI labels services | No | capture button | retained private files/metadata | explicit capture, read-only | click capture/API | Stage 15 controlled capture | IMPLEMENTED | not conversation-grounded | context attachment and result projection | 23 | screen reference E2E |
| 21. OCR | capture OCR endpoint | No | no OCR result control | retention-controlled files | explicit capture/read-only | raw API | Stage 15 backend evidence | IMPLEMENTED | hidden from owner UI/conversation | expose selected OCR result to session | 20 | OCR owner flow |
| 22. Active-window awareness | `ActiveWindowService` API | No | No | none | read-only session metadata | raw API | no real product E2E | IMPLEMENTED | no owner-visible/context route | opt-in active-window context adapter | 20 | window context E2E |
| 23. Shared selected-screen/editor context | no selection adapter | No | No | — | privacy/consent required | none | none | ABSENT | arbitrary selection unavailable | explicit selection/context protocol | 20, 22 | E2E-010/CF-003 |
| 24. Document/private RAG | local document RAG package/CLI | No normal route | No | local indexes | local/private | CLI/API-adjacent | prior backend evidence only | IMPLEMENTED | unavailable in Friday conversation/UI | retrieval source chooser + citations | 3, 7 | supplied-document lesson |
| 25. Video/audio/transcript knowledge ingestion | no product ingestion pipeline found | No | No | — | provenance/privacy needed | none | none | ABSENT | required media knowledge flow absent | local transcript/ingest boundary | 24 | supplied-media E2E |
| 26. Career Forge core | `CareerForgeService`, graph/missions/evidence/attempts | typed information/invocation adapter and active-session handoff | journey panel | CF SQLite | deterministic Learner Twin writes; model cannot mutate or advance mastery | ask Friday to teach/resume/status | physical lesson/attempt/help/evaluation/teach-back/restart/stop flow passed | QUALIFIED | Practice Lab and advanced workspaces remain absent | retain bounded evidence-led loop | 9, 10 | E2E-011/012 |
| 27. Career Forge LEARN | mission brief/loop and lesson-attempt boundary | normal Friday teaching, question, attempt, feedback and teach-back | mission start/resume text | CF SQLite | explicit lesson context; owner pace; no model mastery writes | ask Friday to teach ML | physical teaching and conversational continuity passed | QUALIFIED | no Practice Lab/attempt workspace | Practice Lab later submits into this evidence contract | 26 | E2E-012 |
| 28. Career Forge MAP | competency graph | No | five-item display | CF SQLite | read-only projection | view panel | frontend tests | PARTIAL | incomplete graph/learning navigation | full navigable evidence map | 26 | map and mastery flow |
| 29. Career Forge PROJECTS | mission-project link | No | hard-coded project names + link | CF SQLite | deterministic canonical family | connect button | API/frontend test | PARTIAL | no actual project workspace/artifacts | project workspace and repository link | 16, 26 | E2E-014 |
| 30. Career Forge PROGRESS | canonical bounded progress projection over mission/attempt/assistance/evidence/mastery records | normal Friday progress/history questions | existing PROGRESS panel shows live evidence/retry/help/history/next action | CF SQLite | read-only evidence-derived projection; no percentage or inferred mastery | ask Friday or view panel | real local text progression/history and controlled restart passed | QUALIFIED | retention analytics remain absent | retention view later consumes the same contract | 35 | progress restart E2E |
| 31. Career Forge mission resume | `resume`, ordered attempts and exact resume point | natural voice/text resume handoff | panel reads current mission | CF SQLite | owner-controlled pace; session text is non-durable | ask Friday to resume Career Forge | controlled restart then physical resume recovered canonical mission/evidence state without old transcript | QUALIFIED | broader progress projection remains absent | retain canonical resume boundary | 26 | CF-E2E-001 |
| 32. Career Forge progressive assistance | ordered assistance levels/service | normal Friday hint/help route | No assistance UI | CF SQLite | deterministic minimum next level; complete answer withheld unless final level | ask Friday for a hint | physical prompt then conceptual help passed, including bounded wake-ASR variant | QUALIFIED | richer learning UI remains absent | retain bounded escalation | 27 | CF-E2E-005 |
| 33. Automatic assistance tracking | lesson directive calls `offer_assistance` | normal Friday help route and history question | PROGRESS shows latest recorded help | CF SQLite | deterministic write only, exact content/level retained | ask Friday for a hint | physical hint was spoken and persisted; Slice 4 projection/restart passed | QUALIFIED | richer assistance workspace absent | retain truthful bounded history | 32 | assistance evidence flow |
| 34. Mastery evidence | attempts, semantic assessment, evidence + one-rung advance | normal Friday attempt/check/teach-back and evidence question | PROGRESS shows evidence/mastery truth | CF SQLite | model opinion cannot advance; only correct assessment records typed evidence; explicit one-rung advance remains separate | answer/check or teach back | physical correct quiz evidence, incorrect teach-back retry, no auto-mastery, and Slice 4 projection passed | QUALIFIED | no rich mastery workspace | later render existing records truthfully | 27 | teach/attempt/evidence E2E |
| 35. Retention/review automation | no retention service found | No | placeholder says awaits proof | — | — | none | none | ABSENT | required automation absent | retention scheduler using CF evidence | 30, 50 | CF-E2E-006 |
| 36. Practice Lab | no executable lab | No | No | — | needs code isolation | none | none | ABSENT | core surface absent | isolated editable/run/submit workspace | 16, 27 | E2E-013 |
| 37. Executable coding workspace | executor exists for repos only | No | No | TS/worktrees | exact plan/Git gates | guarded objective only | Stage 17 task | PARTIAL | no learner code workspace | Practice Lab over isolated execution | 36, 48 | E2E-013 |
| 38. Arbitrary code selection context | no selection adapter | No | No | — | explicit privacy/selection | none | none | ABSENT | baseline explicit requirement | selection protocol + session attachment | 23, 36 | CF-E2E-003 |
| 39. Friday-initiated code highlighting/questioning | no editor integration | No | No | — | owner consent/policy | none | none | ABSENT | capability absent | review prompt/action through editor bridge | 38 | CF-E2E-004 |
| 40. Screen-aware tutoring | perception and CF are separate | No | No connected route | separate stores | perception read-only | none | none | PARTIAL | accepted pieces are disconnected | consented capture/selection to tutor context | 20, 26, 38 | CF screen tutoring |
| 41. Interview mode | `TutorMode.INTERVIEW` enum | separate raw tutor endpoint | No | CF SQLite only if assistance recorded | no mastery claim | raw API | unit/backend evidence | IMPLEMENTED | no owner mode/surface/flow | interview workspace and evaluation loop | 27, 34 | CF-E2E-009 |
| 42. Evolving curriculum | dependency graph + local research | No | static next mission | CF/research SQLite | deterministic graph, no autonomous mastery | panel/API | backend acceptance | PARTIAL | research/curriculum not connected to learner behavior | evidence-led curriculum adaptation | 26, 51 | curriculum evidence E2E |
| 43. Project generation/integration | CF project links; Stage 17 executor | No | link only | separate CF/TS stores | execution gates | panel link/API | no integrated E2E | PARTIAL | no actual project lifecycle | connect CF project to guarded repo objective | 29, 48 | project completion E2E |
| 44. GitHub portfolio evidence | GitHub gateway/publication backend | No | No | TS/Git history | review-gated publication | gateway/API | Stage 9 backend evidence | IMPLEMENTED | not Career Forge/owner surfaced | CF evidence workflow to gateway | 43, 45 | E2E-014 |
| 45. Public-evidence approval gate | task approval/publication boundaries | No | No | task history | explicit approval/auth | gateway/API | accepted backend gates | IMPLEMENTED | no visible owner workflow | render truthful review/publish gate | 44 | public evidence approval E2E |
| 46. General repository understanding | CodeRAG/index/planner | No normal conversation route | No | indexes | read-only inspection | CLI/gateway | prior backend tests | IMPLEMENTED | not discoverable/invokable conversationally | capability router to safe repo query | 9, 10 | repo explain E2E |
| 47. Coding/debugging/refactoring | roles/planner/executor | no intent router; roles only prompt contexts | objective panel planning only | TS/audit/worktrees | exact approval/isolation/validation | gateway/CLI/objective | Stage 17 controlled execution | IMPLEMENTED | not natural Friday coding mode | conversation-to-guarded objective bridge | 46, 48 | bounded engineering E2E |
| 48. Autonomous objectives | `ObjectiveService` | No | create/plan/cancel console | autonomy SQLite + TS | credentials/exact approval/isolation | UI form/API | Stage 17 live controlled task | INTEGRATED | disconnected from conversation and execution control deliberately hidden | natural objective creation/status while preserving gate | 9, 47 | E2E-016 |
| 49. Long-running objective progress | task/objective projections | No | polling bounded panel | autonomy/TS | read-only projection | UI | Stage 17 task evidence | PARTIAL | no rich owner progress/recovery narrative | event-linked progress/status | 48, 53 | long task E2E |
| 50. Proactive watches/notifications | `ProactiveEventEngine` | event only, no conversational action | no frontend component | proactive SQLite | observe/notify only | configured watch/API | Stage 18 controlled live | IMPLEMENTED | not owner-configurable/visible in UI | notification center and safe watch setup | 9 | E2E-017 |
| 51. Research/self-learning | `ResearchService` | No | No | research SQLite | owner-provided sources only | raw API | Stage 20 backend acceptance | IMPLEMENTED | no product knowledge workflow | source/research workspace + conversation route | 24, 42 | supplied-source E2E |
| 52. Owner-habit adaptation | memory preferences can store facts | No automatic adaptation | No | memory SQLite | explicit owner records only | API/CLI | none | PARTIAL | no preference learning/transparent control | opt-in preference behavior and controls | 7, 8 | preference/restart E2E |
| 53. History/audit | task history, desktop audit, memory lifecycle | No unified query | objective/desktop fragments | multiple SQLite stores | subsystem boundaries | disparate UI/API/CLI | Stage-specific evidence | PARTIAL | no unified "what happened" product view | cross-boundary read-only activity projection | 48, 50, 55 | E2E-015 |
| 54. Explain what Friday did | task artifacts/audits exist | No natural question route | partial objective outcome | TS + journals | audit read-only | API/CLI | task evidence only | PARTIAL | no unified explanation | capability-aware activity narrator grounded in records | 53 | E2E-015 |
| 55. Undo/rollback | executor rollback/checkpoints; no unified undo | No | No | TS/checkpoints | guarded scope | task recovery/CLI | Stage 8/17 evidence | IMPLEMENTED | owner-visible undo unavailable | reversible-action ledger + safe undo routes | 17, 53 | E2E-008/015 |
| 56. Interruption/crash recovery | worker recovery, TS/objective recovery | No owner narrative | health/objective partial | journals/SQLite | fail-closed recovery | service/CLI | Stage 12/17 controlled recovery | IMPLEMENTED | no integrated owner-visible recovery | unified truthful recovery projection | 49, 53 | E2E-020 |
| 57. Model replaceability | `LocalLLM` adapter + roles | Yes through adapter | uses presentation service | config | ADR 0014 one model | configuration/deployment | architecture + unit tests | IMPLEMENTED | baseline swap suite not run | codify model-swap qualification suite | 3, 8, 27, 47 | E2E-019 |
| 58. Offline operation | local Qwen/memory/RAG design | core path local | UI local | local state | ADR 0014 | normal local use | partial historic evidence | PARTIAL | no integrated offline product proof | execute baseline offline scenario | 7, 24, 57 | E2E-018 |
| 59. Local Intelligence Sovereignty | ADR 0014, local services | yes | yes | owner local | no paid/cloud core | normal runtime | architecture/accepted stages | IMPLEMENTED | product-level offline proof still missing | preserve; qualify end-to-end | 58 | E2E-018 |
| 60. Frontend workspace/navigation completeness | React cinematic root and five fixed consoles | composer only | single-page fixed panels, no navigation | browser state + APIs | presentation has no authority | browser | build/tests only | PARTIAL | decorative/narrow panels; missing connected workspaces | connected navigable workspaces with truthful state | 26, 36, 50, 53 | UI flow qualification |

## Reproduction of owner-observed gaps

| Gap | Evidence found | Classification | Consequence for remediation |
|---|---|---|---|
| GAP-001 one-shot voice | `FridayWakeVoiceOrchestrator.handle_wake_utterance()` and `FridayManagedWakeVoice._run_voice_turn()` both resume wake capture in `finally`; the accepted architecture explicitly defines wake -> one turn -> resume. | Confirmed architectural mismatch | Build continuous session ownership before changing voice components. |
| GAP-002 repeated wake | Bare wake has only one 8-second follow-up capture; after its response the wake loop resumes. No active-session listener exists. | Confirmed architectural mismatch | Same foundational session slice as GAP-001. |
| GAP-003 apparent memory absence | Conversation retrieves only `memory.search(current_prompt, limit=5)` and has no transcript/history; writes require explicit complete API records. | Confirmed partial integration | Couple bounded active context with explicit durable-memory behavior/control. |
| GAP-004 Career Forge denial | CF has API/UI/backend but no capability registry or conversation grounding; default prompt is generic Friday. | Confirmed missing integration | Registry/self-awareness is required before CF product work. |
| GAP-005 backend/frontend disconnect | Many presentation endpoints have no frontend client/component; CF tutor, memory, research, proactive, desktop proposals, perception results and repo tools lack normal conversation routes. | Confirmed | Route capabilities through a single truthful conversation/policy boundary. |
| GAP-006 narrow cinematic UI | `App.tsx` mounts fixed console cards; CF panel is a bounded projection and other accepted services have no workspace. | Confirmed | Add only real connected workspaces after foundational routes exist. |
| GAP-007 approval friction | Desktop actions require proposal + dialog + API approval + one-time execution even for allowlisted launch/open; current frontend cannot create the proposal. | Confirmed for current scope; target policy undecided | Define low-risk explicit-command policy without weakening high-risk gates. |

## Slice 1 evidence (2026-09-12)

The real local Friday service was used, not synthetic audio. A live conversation
correctly stated that Career Forge is integrated and that its Practice Lab is not
installed; a subsequent reference question resolved the prior answer from active
session context. The read-only capability endpoint reported the same state.

Physical voice testing proved wake-once follow-up conversation and a natural
pause. A trusted barge-in stopped playback in about 3.3 ms. An ASR near miss for
an attempted stop during barge-in remained normal conversation, as required by
the exact-stop safety boundary; it was not broadened into an unsafe alias. The
final physical `Stop.` run produced `voice_explicit_stop` at event sequence 57,
left runtime IDLE with zero active session turns, no later user conversation
event, no voice turn, and healthy capture.

An explicit temporary durable-memory record was recalled through the normal local
conversation path, removed through its governed lifecycle, and the SQLite
database passed `PRAGMA integrity_check` after controlled service restart. This
does not claim natural-language durable-memory capture.

### Slice 1 regression repair — current-discussion memory (2026-09-12)

Owner qualification found that the phrase “What do you remember about Career
Forge from our discussion?” could be answered as though only durable memory
counted, despite active-session turns being present. The session data was not
missing: prompt composition lacked an evidence-priority instruction and placed
durable-memory context before the generic active-history label. The repair makes
the current owner prompt immediate, active history primary for current-discussion
references, durable memory explicitly long-term, and capability state descriptive.
It preserves all distinct provenance and mutation boundaries.

Focused deterministic coverage exercises active-only, durable-only, both-source,
and post-close cases. Real local Qwen returned a turn-by-turn Career Forge
summary for the exact owner wording and stated that it referred to the current
conversation rather than permanent memory. Physical voice requalification passed
the same six-turn flow; final exact stop was event sequence 1729, with runtime
IDLE, zero active session turns, and healthy wake capture.

## Dependency-aware remediation plan

1. **Foundational Friday coherence:** add the typed capability registry and
   conversation grounding, then a bounded continuous-session/context controller
   that preserves the accepted interaction lease, explicit stop, barge-in, and
   wake recovery. Integrate behavioral memory and expose a truthful unified
   activity/recovery projection. This is the recommended first implementation
   slice because it directly unlocks GAP-001 through GAP-005 without expanding
   desktop authority.
2. **Safe agency and shared context:** design evidence-backed low-risk explicit
   launch/open/navigation and owner-consented perception/selection routes. Keep
   high-risk mutation, package install, deletion, keyboard/mouse, and execution
   behind distinct policy/approval/rollback designs.
3. **Career Forge advanced integration:** build the real tutor loop and Practice
   Lab on the coherent session/context boundary; then connect arbitrary
   selection, screen context, assistance/evidence/retention/progress, projects,
   interview mode, and approval-gated GitHub evidence.
4. **Product UI integration:** evolve the cinematic shell into navigable,
   connected workspaces for conversation/activity, memory, Career Forge,
   perception, agency, objectives, research, and notifications. No decorative
   disconnected tabs.
5. **Builder-side reality qualification:** run the baseline E2E scenarios by
   affected slice, remediate evidence-backed failures, run full regression once
   stable, and freeze the release candidate. Independent Astra qualification is
   explicitly out of scope until owner authorization.

## Audit conclusion

The accepted repository is a strong collection of local, bounded backend
capabilities, but it is not yet a qualified coherent Friday product. The highest
severity product gaps are the one-shot session architecture, missing active
conversation context, absent capability self-awareness, lack of natural routes
to accepted capabilities, and missing Career Forge interactive surfaces. No
broad remediation was performed by this audit.
