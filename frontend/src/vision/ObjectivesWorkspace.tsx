import { ObjectiveConsole } from "../components/ObjectiveConsole";
import { SectionHeader } from "./ui";

export function ObjectivesWorkspace() {
  return (
    <section className="op-objectives-canonical">
      <SectionHeader
        eyebrow="YOUR WORK"
        title="Automate"
        description="Set a goal, see Friday’s progress, and review the outcome."
      />
      <details className="op-objectives-authority">
        <summary>How Automate works</summary>
        Objective and linked task status come from Friday's local services. Activity is a bounded projection of persisted objective and task history, not a complete audit export. Plan review is read-only here; approval and execution remain in their existing governed task-history and gateway paths.
      </details>
      <ObjectiveConsole />
    </section>
  );
}
