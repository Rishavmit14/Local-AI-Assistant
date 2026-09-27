import { ObjectiveConsole } from "../components/ObjectiveConsole";
import { SectionHeader } from "./ui";

export function ObjectivesWorkspace() {
  return (
    <section className="op-objectives-canonical">
      <SectionHeader
        eyebrow="FRIDAY / LOCAL OBJECTIVES"
        title="Objectives"
        description="Create a bounded intention, follow Friday's canonical planning state, and review the linked task outcome."
      />
      <div className="op-objectives-authority" role="note">
        Objective and linked task status come from Friday's local services. Activity is a bounded projection of persisted objective and task history, not a complete audit export. Plan review is read-only here; approval and execution remain in their existing governed task-history and gateway paths.
      </div>
      <ObjectiveConsole />
    </section>
  );
}
