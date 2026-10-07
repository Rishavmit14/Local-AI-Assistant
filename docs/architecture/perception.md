# Friday visual perception

## Stage 15 foundation

Screen awareness is explicitly owner-initiated and read-only. The existing
`ScreenCaptureService` invokes the GNOME Shell `org.gnome.Shell.Screenshot`
session-bus method; `capture_with_consent()` falls back to the desktop
Screenshot portal when session-bus capture is denied. Both paths are on demand,
including when the Owner asks a live voice screen question; Friday does not
continuously capture the screen. It writes a PNG only under the configured
`var/perception` directory and returns provenance-safe metadata (capture id,
time, hash, byte size, and source), never the image path or raw pixels through
the API.

The capture service has no keyboard, mouse, window-management, shell, upload,
or desktop-control authority. Capture failure removes incomplete
files. Images are generated private state and must never be committed. A local
SQLite metadata index retains only capture id, timestamp, hash, size, and source;
the capture service purges both pixels and metadata after its bounded retention
window. OCR, screen interpretation, active-window context, and the cinematic
projection remain subsequent Stage 15 work. A retained capture can be sent to
the existing local Tesseract stack only by an explicit request; text is bounded,
not persisted by the perception boundary, and unavailable after retention purge.
An explicit UI-state route derives only deterministic OCR hints (`no_readable_text`,
`text_present`, `code_like`, or `error_like`) with matching keyword evidence. It
does not make semantic vision claims or invoke a general-purpose model.
An explicit retained capture may also be classified by the optional local
`google/vit-base-patch16-224` specialist. The CPU-only classifier loads only a
pre-existing snapshot from the configured local cache; it never downloads a
model, sends image data over the network, persists labels, or calls Qwen. It
returns at most ten label/confidence pairs for that retained capture. The
specialist is a narrow image classifier, not a second general-purpose model.
Active-window context uses a single hard-coded GNOME Shell focus query and never
accepts a caller-supplied expression. On hosts that disable the query it reports
`unavailable`; it does not attempt focus, enumeration, or any control fallback.
Any later Stage 16 action uses an independent policy-governed desktop-control
boundary.

The existing cinematic Friday UI projects capture status and retained metadata.
Its capture control is an explicit owner action; it never receives raw image
data, image paths, OCR text, or any desktop-control capability.

When the desktop requires its native screenshot UI, the owner may explicitly
save an image and use `local-ai-perception ingest <image>`. The command copies
only that selected local PNG/JPEG into private retention-controlled storage and
records source provenance as `owner-selected-local-file`; it does not retain a
link to the external source.

On the current GNOME/Wayland host, direct session-bus capture is denied by the
desktop privacy policy. The Stage 26 candidate uses the desktop Screenshot
portal as an explicit capture fallback. A live portal request returned a local
image; the service copied it into retained state and removed the disposable
qualification copy afterward. Portal denial remains a bounded failure. This
does not grant RemoteDesktop input permission or continuous screen streaming.
Capture storage is tightened to a 0700 directory and 0600 image/SQLite files;
the portal's temporary source remains managed by the desktop portal.
The presentation capture, metadata, active-window, OCR, UI-state, and label
routes now require the existing local Owner browser session; mutations require
the canonical loopback Origin and CSRF check. The Perception and System clients
restore that session through the accepted local Owner bridge and retry a single
expired-session response. No Gateway action scope is inferred from observation.
Stage 26 owner-requested screen accounts exclude GNOME's decorative
`mutter-x11-frames` and `gnome-shell` active frames when selecting one real
application window. A live disposable GTK window was then identified by app,
title and the visible `Details ready` label; a private desktop Screenshot
portal capture and local OCR were available. The account states that visible
metadata cannot establish unseen work or intent. No image-native Qwen vision
claim is made from this structured AT-SPI/OCR path.

## Session 2 — fresh screen context in normal voice

The live-vision voice route reuses this capture and observation machinery; it
does not add a second screenshot subsystem. A routed visual screen question
captures after the request begins, rejects a capture whose timestamp predates
that request, collects one fresh AT-SPI observation, queries the active window,
and combines up to 60 relevant visible semantic elements, 16 monitor records,
bounded local OCR, and an optional local visual-model description. An AT-SPI
result with an older timestamp is discarded. The packet records capture and
observation identity/digests, timestamps, app/window/focus, and a change
fingerprint. Prior packet content is used only to report whether the screen
changed; it is never reused as current answer evidence. Screen packet/audit
content lives in a private 0700 directory with a 0600 SQLite file and a
15-minute retention window; image paths are not recorded in that audit.

The current primary Qwen endpoint is text-only. When enabled, a separate
`LocalVisionCortex` sends a resized JPEG only to an authenticated llama.cpp
server on `127.0.0.1`; the host loads Qwen2.5-VL-3B and its separate GGUF
`mmproj` projector on CPU, leaving the 8 GB GPU available to the primary Qwen.
The cortex returns a short description, which Friday includes as untrusted
evidence text in the main Qwen prompt. Main Qwen never receives image bytes.
The cortex cannot call desktop tools or authorize actions, and the normal Friday
runtime remains useful without the optional service. Its request is preceded by
a fresh capture; semantic-only app/window/focus questions skip capture, OCR and
vision inference. Detectable sign-in/verification text suppresses OCR text and
visual inference for that turn. The visual-model client rejects non-loopback
URLs and verifies the server's multimodal capability/model alias before sending
pixels.

Owner qualification used real microphone turns after a candidate voice-service
restart. Friday described a revenue canvas and then a distinct warehouse
inventory canvas from new captures, and explained a visible Python
`ZeroDivisionError`; the canvas values were not available from AT-SPI alone.
The visual service runs Qwen2.5-VL-3B locally on CPU with a 512-token image cap.
On one retained chart frame, the tuned 1024px/512-token configuration took
29.2s and retained all chart labels and values. An earlier 768px run with a
1024-token minimum took 73.7s and missed labels; both edge size and token budget
changed, so this is a combined-configuration comparison. The physical terminal
turn measured 39.9s for visual inference and 102.3s through completed playback.
That turn was accurate but too slow to call conversational; VLM and primary
Qwen latency remain a known limitation. Private screen and event evidence is
kept outside Git under the owner-only Friday state directory.
