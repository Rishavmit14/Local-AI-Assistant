# NeetCode visual reference for Friday

**Reference checked:** 2026-10-06 against the live public NeetCode Courses, Practice, and Roadmap surfaces. **State:** The Owner approved the Stage 28 UI on 2026-10-14; publication and live qualification are recorded in `FINAL_NEETCODE_PARITY_AND_PRODUCT_AUDIT.md`. Whole-product qualification remains open. This is a measured visual guide, not a claim of whole-product parity.

## Reference measurements

| Element | Live reference | Friday candidate target |
|---|---:|---:|
| Global header | 56 px | 56 px |
| Courses contextual menu | x=44, y=88, 240 × 92 px | x=44, y=88, 240 px wide; height follows Friday's secondary routes |
| Practice category rail | x=12, y=88, 280 px wide | 64 px icon rail below 1050 px; full menu above it |
| Main content start | x≈300 px at 1440 px viewport | x=300 px |
| Main content right edge | x≈1392 px at 1440 px viewport | x=1392 px |
| Course cards | about 280 × 305 px | Three 256 × 299 px shared cards in the 796 px Home column at 1440 px; 280 px cards on Learn and Practice recommendations |
| Course artwork | about 158 px tall | Original inline SVG artwork uses a 16:9 top panel (about 144 px on Home cards) above a roughly 152 px content body |
| Header / tab controls | 56 px / 32–36 px | 56 px / 34 px |
| Common card radius | 12 px | 12 px |
| Practice side panel | 280 px | 280 px Home evidence/activity column on wide screens |

The NeetCode reference comparison and 68 comparison composites are from the 2026-10-06 visual study. On 2026-10-11, the Stage 28 candidate checked all 16 Friday routes at five viewport targets—1440 × 900, 1280 × 800, 768 × 1024, 390 × 844, and 320 × 740—for visible headings, mobile navigation, and horizontal overflow. That is route-layout evidence, not 80 saved screenshots. Representative screenshots were reviewed for desktop Home, mobile Home, and narrow Settings; no raw screenshots were added to Git. At 320 px, Settings theme choices and links stack to remain visible.

## Color and type tokens

Measured/visually sampled from the live dark NeetCode surface:

| Token | Reference value |
|---|---|
| Canvas | `oklch(0.23 0.0043 308.193)` |
| Card | `oklch(0.22 0 0)` |
| Raised surface | `oklch(0.28 0 0)` |
| Border | `oklch(0.345 0 0)` |
| Primary text | `oklch(0.9672 0 0)` |
| Accent | `oklch(0.673 0.182 276.935)` |
| Body text | 14–16 px, regular |
| Card title | about 15 px, semibold |
| Section heading | about 18 px, semibold |
| Page heading | 32 px in Courses; 48 px on Practice |
| Metadata | about 10–12 px |
| Spacing rhythm | 8 / 12 / 16 / 24 / 32 px |

The live site uses a compact dark header, charcoal cards with subdued borders, violet selected/primary states, compact icon-led controls, and responsive course/practice lists. NeetCode Home was signed out and showed a marketing landing page, so it is only a visual-language reference; no personal dashboard layout or learner progress was inferred.

## Friday application

Friday keeps its brand, functionality, data, safety boundaries, and route names. Its top bar presents Home, Learn, Practice, Roadmap, Projects, Career, and Research. The left panel presents secondary destinations and settings without repeating the top-level destinations. Search/Browse remains the route to all additional Friday workspaces.

Home now uses three portrait-style cards (learning, project, and Career Forge next step) in its 796 px main column beside a 280 px evidence/activity rail. At 1440 × 900 the cards measure 256 × 299 px at x=300, 570, and 840; their original inline SVG artwork is 16:9 and the shared card body is about 152 px tall. The measured NeetCode Courses card is about 280 × 305 px, so Friday's cards are narrower to preserve its real evidence rail. The rail shows only backend-supported evidence and recorded activity. Empty path, project, and activity states remain empty; no learner progress is seeded. `NeuralPresence` keeps its geometry, materials, shaders, and normal-mode animation; reduced-motion mode freezes movement and snaps state cross-fades.

Career readiness uses a compact ring backed by Friday's independent-competency and total-competency fields, echoing NeetCode's visible progress widget. It shows the recorded numerator/denominator with an accessible progress value; zero evidence remains an empty ring. No completion or learner state is inferred from the illustration artwork.

Practice Lab's mission-required state is a compact entry panel with a direct Learn action and its real workflow: read the lesson, work in the editor, then run tests and review. When the canonical Career Forge read model returns a next lesson, the shared course card shows its real title, reason, and next action; if the read model has no recommendation or is unavailable, no substitute card appears. A problem catalog is not shown without a selected mission. The service-error state remains separate and retryable.

The four actual Career Forge project pathways now use the shared illustrated course-card anatomy with their real focus and learning/skill link counts. The artwork is decorative; it does not claim project progress. Assigned-project, objective, evidence, review, and publication controls retain their existing canonical data and authorization gates. The current candidate fixture has no linked learning missions or assigned projects, so those gated actions are not shown in the current comparison.

Learn, Project, Progress, and evidence cards share the same charcoal surfaces, border, radius, original diagrams, and compact metadata hierarchy instead of mixing legacy panels with the NeetCode palette.

At 1051–1200 px the Home overview keeps a 220 px progress/activity rail beside two course cards; the additional 1121 × 950 QA capture fits without document overflow. At 1050 px and below the left navigation becomes a compact rail and the Home overview stacks; mobile uses the compact bottom navigation and single-column cards. The rail can also be collapsed on desktop.

The learning Roadmap uses a dotted canvas behind the recorded prerequisite graph, with compact skill cards, visible connector paths, and current/next-up emphasis. The current learner data yields three competency nodes, while NeetCode's reference displays a much larger 150-problem map; Friday leaves the graph sparse rather than adding fictitious curriculum. Mastery, prerequisite descriptions, and internal competency details remain tied to Career Forge data; only IDs stay behind Advanced details. Projects use the shared card system separately.

At mobile widths the horizontally scrollable Learn/Roadmap/Practice/Interview/Progress navigation scrolls the current section into view. The 390 × 844 pass verified the selected Progress tab is fully visible.

## Known visual differences and open evidence

- Friday's seven primary destinations and secondary tools carry more navigation than NeetCode's signed-out Courses menu.
- Friday Home contains learning, project, Career Forge, and evidence content; the NeetCode public Home reference is marketing content.
- The NeetCode public Home is marketing content; Friday Home is an authenticated, data-backed workspace. Its hierarchy borrows NeetCode's feature card, course artwork, compact tiles, dark surfaces, and measured spacing without implying dashboard parity or inventing progress.
- Practice Lab has no problem catalog until Friday loads a selected learning mission; the entry remains a mission-required state with a real Career Forge recommendation when available.
- Friday Roadmap has three current learner competency nodes versus NeetCode's much larger problem map. Project pathways have no linked or assigned work in the current candidate state, so publication actions remain behind their normal mission/evidence/owner-approval requirements.
- The current responsive pass checks all 16 destinations at five exact viewport targets. Representative keyboard routes and focus behavior passed; reduced-motion CSS, media-query propagation, and shader-transition behavior are covered by tests. The host browser cannot emulate its native reduced-motion media preference here, so a full reduced-mode browser capture remains unavailable. Stage 28 Owner visual acceptance is qualified; populated owner-flow visuals and whole-product qualification remain open.
