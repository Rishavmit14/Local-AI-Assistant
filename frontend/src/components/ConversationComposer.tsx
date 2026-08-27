import {
  useMemo,
  useState,
} from "react";

import type { FormEvent } from "react";

import type {
  FridayConnectionState,
  FridayRuntimeState,
} from "../runtime";

interface ConversationComposerProps {
  runtimeState: FridayRuntimeState;
  connectionState: FridayConnectionState;
  assistantText: string;
  error: string | null;
  sendConversation: (prompt: string) => Promise<void>;
}

const BUSY_STATES = new Set<FridayRuntimeState>([
  "thinking",
  "retrieving",
  "planning",
  "waiting_for_approval",
  "executing",
  "validating",
  "reviewing",
  "speaking",
]);

export function ConversationComposer({
  runtimeState,
  connectionState,
  assistantText,
  error,
  sendConversation,
}: ConversationComposerProps) {
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const disabled = useMemo(
    () =>
      submitting ||
      connectionState !== "connected" ||
      BUSY_STATES.has(runtimeState),
    [connectionState, runtimeState, submitting],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const value = prompt.trim();

    if (!value || disabled) {
      return;
    }

    setSubmitting(true);
    setPrompt("");

    try {
      await sendConversation(value);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="conversation-layer" aria-label="Friday conversation">
      {assistantText ? (
        <div className="assistant-response" aria-live="polite">
          <div className="assistant-response-label">FRIDAY</div>
          <div className="assistant-response-text">{assistantText}</div>
        </div>
      ) : null}

      {error ? (
        <div className="conversation-error" role="alert">
          {error}
        </div>
      ) : null}

      <form
        className="conversation-composer"
        onSubmit={handleSubmit}
      >
        <span className="composer-prompt">&gt;</span>

        <input
          className="composer-input"
          type="text"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder={
            connectionState === "connected"
              ? "Speak to Friday..."
              : "Connecting to Friday..."
          }
          disabled={connectionState !== "connected"}
          autoComplete="off"
          spellCheck={false}
          aria-label="Message Friday"
        />

        <button
          className="composer-submit"
          type="submit"
          disabled={disabled || !prompt.trim()}
          aria-label="Send message"
        >
          <span>TRANSMIT</span>
          <span className="composer-arrow">↗</span>
        </button>
      </form>
    </section>
  );
}
