# Friday visual perception

## Stage 15 foundation

Screen awareness begins as an explicitly owner-initiated, read-only local
capture. `ScreenCaptureService` invokes the GNOME Shell session screenshot
interface only when the local presentation endpoint is called. It writes a PNG
only under the configured `var/perception` directory and returns provenance-safe
metadata (capture id, time, hash, byte size, and source), never the image path or
raw pixels through the API.

The capture service has no keyboard, mouse, window-management, shell, upload,
model, OCR, or desktop-control authority. Capture failure removes incomplete
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
Active-window context uses a single hard-coded GNOME Shell focus query and never
accepts a caller-supplied expression. On hosts that disable the query it reports
`unavailable`; it does not attempt focus, enumeration, or any control fallback.
Any later Stage 16 action uses an independent policy-governed desktop-control
boundary.

The existing cinematic Friday UI projects capture status and retained metadata.
Its capture control is an explicit owner action; it never receives raw image
data, image paths, OCR text, or any desktop-control capability.

On the current GNOME/Wayland host, direct session-bus capture is denied by the
desktop privacy policy. Friday returns only a bounded permission-required result;
it cannot bypass that control. A physical owner approval through the desktop's
capture-consent flow is required for live capture qualification.
