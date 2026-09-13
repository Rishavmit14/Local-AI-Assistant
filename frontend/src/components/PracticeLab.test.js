import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const component = readFileSync(resolve(import.meta.dirname, "PracticeLab.tsx"), "utf8");
const styles = readFileSync(resolve(import.meta.dirname, "../App.css"), "utf8");

describe("Practice Lab primary workspace contract", () => {
  it("portals the workspace outside the Career Forge sidebar", () => {
    expect(component).toContain("createPortal(workspace, document.body)");
    expect(component).toContain('data-workspace="primary"');
  });

  it("keeps the owner controls and close return action in the workspace", () => {
    for (const label of ["RUN", "TEST", "SUBMIT", "ASK FOR A HINT", "CLOSE LAB"]) {
      expect(component).toContain(label);
    }
    expect(component).toContain("setLab(null)");
  });

  it("reserves a desktop-sized primary editor rather than a sidebar width", () => {
    expect(styles).toContain("grid-template-columns: minmax(620px, 1fr) minmax(310px, 380px)");
    expect(styles).toContain("z-index: 120");
  });
});
