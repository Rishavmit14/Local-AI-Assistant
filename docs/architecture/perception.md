# Friday visual perception

## Stage 15 foundation

Screen awareness begins as an explicitly owner-initiated, read-only local
capture. `ScreenCaptureService` invokes the GNOME Shell session screenshot
interface only when the local presentation endpoint is called. It writes a PNG
only under the configured `var/perception` directory and returns provenance-safe
metadata (capture id, time, hash, byte size, and source), never the image path or
raw pixels through the API.

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
desktop privacy policy. Friday returns only a bounded permission-required result
and cannot bypass that control. The owner-selected native screenshot route has
qualified a retained capture locally; the direct GNOME route remains unavailable
until the desktop grants its own consent.
