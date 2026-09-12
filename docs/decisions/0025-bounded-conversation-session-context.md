# ADR 0025: Bounded Conversation Session Context

## Status

Accepted — 2026-09-12

## Decision

Friday owns an in-process active-session record rather than treating each voice turn as an isolated interaction or treating the frontend transcript as truth. It retains at most 16 owner/Friday turns and 12,000 characters. Voice follow-up capture remains available for a configured 60-second idle window (bounded to 15–300 seconds), then clears the session and returns to strict wake mode.

Durable `FridayMemoryService` is separate. Session records clear on close and restart. Retrieved memory is untrusted reference context; neither session turns nor model output may write persistent memory. A typed capability registry supplies descriptive state to conversation but grants no capability authority.

## Consequences

The owner can speak naturally after one wake without an unbounded microphone lifecycle or competing microphone readers. Exact explicit stop, natural barge-in, interaction ownership, recovery, and strict wake semantics are preserved. No second general-purpose model, cloud dependency, or automatic durable-memory mutation is introduced.
