import { ObjectiveConsole } from "../components/ObjectiveConsole";
import { SectionHeader } from "./ui";

export function ObjectivesWorkspace() {
  return (
    <section className="op-objectives-canonical">
      <SectionHeader
        eyebrow="INTENT INTO MOMENTUM"
        title="Your momentum"
        description="Give your next chapter a direction. Let Friday help move it forward."
      />
      <div className="db-momentum-path" aria-label="The work journey"><span><b>01</b> Set your intention</span><i/><span><b>02</b> Shape the plan</span><i/><span><b>03</b> Make progress</span><i/><span><b>04</b> Reflect & grow</span></div>
      <details className="op-objectives-authority">
        <summary>How goals and activity work</summary>
        Objective and linked task status come from Friday's local services. Activity is a bounded projection of persisted objective and task history, not a complete audit export. Plan review is read-only here; approval and execution remain in their existing governed task-history and gateway paths.
      </details>
      <ObjectiveConsole />
    </section>
  );
}
