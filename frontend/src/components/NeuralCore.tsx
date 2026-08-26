import type { FridayRuntimeState } from "../runtime";

interface NeuralCoreProps {
  state: FridayRuntimeState;
}

const STATE_LABELS: Record<FridayRuntimeState, string> = {
  sleeping: "DORMANT",
  idle: "ONLINE",
  listening: "LISTENING",
  transcribing: "TRANSCRIBING",
  thinking: "THINKING",
  retrieving: "RETRIEVING",
  planning: "PLANNING",
  waiting_for_approval: "AWAITING APPROVAL",
  executing: "EXECUTING",
  validating: "VALIDATING",
  reviewing: "REVIEWING",
  speaking: "SPEAKING",
  completed: "COMPLETE",
  error: "FAULT",
  cancelled: "CANCELLED",
};

export function NeuralCore({ state }: NeuralCoreProps) {
  return (
    <section
      className="neural-stage"
      data-state={state}
      aria-label={`Friday ${STATE_LABELS[state]}`}
    >
      <div className="ambient-field" />

      <div className="orbital orbital-outer">
        <span />
        <span />
        <span />
      </div>

      <div className="orbital orbital-middle">
        <span />
        <span />
      </div>

      <div className="orbital orbital-inner" />

      <div className="core-halo halo-outer" />
      <div className="core-halo halo-middle" />

      <div className="neural-core">
        <div className="core-surface" />
        <div className="core-energy" />
        <div className="core-center" />
      </div>

      <div className="axis axis-horizontal" />
      <div className="axis axis-vertical" />

      <div className="state-readout">
        <span className="state-mark" />
        <span>{STATE_LABELS[state]}</span>
      </div>
    </section>
  );
}
