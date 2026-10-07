# ADR 0047: local visual cortex for voice screen context

- Status: accepted after physical Session 2 qualification
- Date: 2026-10-07

## Context

Stage 26 already provides fresh local screen capture, bounded AT-SPI
observation, active-window metadata and monitor geometry. Normal voice questions
did not use those observations. The loaded Qwen3.6 35B primary model advertises
text-only modalities, so routing a screenshot to it would be unsupported and
claiming that OCR/AT-SPI alone provides pixel understanding would overstate the
product.

The owner-requested machine has an 8 GB GTX 1070 already occupied by the
primary Qwen server, 30 GiB system memory, and a local llama.cpp build with
multimodal support. Qwen2.5-VL-3B fits a separate CPU-only inference service
with a GGUF `mmproj` projector, avoiding a second general-purpose reasoning
model and GPU contention. The initial synthetic non-accessible chart probe
described its title and values; subsequent physical probes confirmed canvas
chart reading and visible terminal-error explanation.

## Decision

Route only normal voice turns classified as screen-context questions through a
fresh `ScreenContextService`. Semantic app/window/focus questions collect fresh
AT-SPI/window data without pixels. Visual questions capture after request start,
reject stale capture and accessibility timestamps, and gather bounded OCR and
visual-model evidence. Previous packets may support a changed-screen indicator
but are never reused as answer evidence.

Keep Qwen as Friday's primary reasoning/orchestration brain. A separate
`LocalVisionCortex` may send a resized local capture only to an authenticated
HTTP loopback llama.cpp service that has positively advertised image support
and the configured model alias. The service uses Qwen2.5-VL-3B plus its
projector on CPU; its short text result and local semantic/OCR evidence are
passed to Qwen as untrusted observations. The visual endpoint is disabled by
default, uses a private bearer token when enabled, and has no desktop action
capability. Failure to obtain fresh pixels or visual evidence yields an honest
bounded response and never a stale-screen fallback or upload request.

Private screen packets retain bounded text/evidence for 15 minutes under
`var/perception` with owner-only directory/database permissions and no stored
pixel path. Detectable password/verification prompts suppress OCR text and
visual inference. Existing screenshot storage retains its own bounded private
pixels. The lightweight semantic observer stays on-demand in the current
implementation; a dedicated always-running monitor is deferred until measured
need justifies it.

## Consequences

- A true pixel model is used for charts, diagrams, canvas content and other
  inaccessible UI; OCR and AT-SPI complement it rather than substitute for it.
- The local CPU service stays warm. Its production unit caps image tokens at
  512. A same-frame run at 1024px with that cap took 29.2s and recovered all
  chart labels and values; an earlier 768px run under the server's 1024-token
  minimum took 73.7s and missed labels. Because both edge size and token budget
  changed, this compares the combined tuning, not the isolated token-cap
  effect. The later physical terminal turn measured 39.9s for the visual stage
  and 102.3s through completed playback. This is correct but not
  conversational latency; local VLM inference and primary-Qwen generation are
  the dominant delays. The route speaks a short acknowledgement first and
  records phase timestamps for follow-up optimization.
- The main Qwen endpoint and its accepted model boundary remain unchanged.
- Two fresh physical screen questions described different canvas-only charts;
  a third physically asked why the visible Python terminal was failing and got
  the correct `ZeroDivisionError` explanation. The second chart used a new
  capture and observation identity. Persistent screen permission worked after
  the candidate voice service restart. The Milestone A regression and final
  repository gates are required before publication.

## Evidence and follow-up

Private physical evidence is stored in
`/home/kumar-rishav/.local/state/friday-live-vision/` with owner-only
permissions; screenshots, OCR text, credentials and raw logs are not committed.
The accepted repository records the bounded result and latency, not those
private screen contents. Full regression, local secret/recovery checks and
remote publication are recorded in the Session 2 handoff and history.
