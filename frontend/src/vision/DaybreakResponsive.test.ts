import { describe, expect, it } from "vitest";
// @ts-expect-error Vitest runs this source-only regression in Node; the app bundle does not use Node APIs.
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("./DaybreakResponsive.css", import.meta.url), "utf8");
const daybreakCss = readFileSync(new URL("./Daybreak.css", import.meta.url), "utf8");
const capabilityCss = readFileSync(new URL("../presentation/CapabilityField.css", import.meta.url), "utf8");

function mediaBlocks(maxWidth: number): string[] {
  const marker = `@media (max-width: ${maxWidth}px)`;
  const blocks: string[] = [];
  let offset = 0;
  while (true) {
    const start = css.indexOf(marker, offset);
    if (start < 0) return blocks;
    const open = css.indexOf("{", start + marker.length);
    let depth = 0;
    let end = open;
    for (; end < css.length; end += 1) {
      if (css[end] === "{") depth += 1;
      if (css[end] === "}" && --depth === 0) break;
    }
    blocks.push(css.slice(open + 1, end));
    offset = end + 1;
  }
}

describe("Daybreak responsive regressions", () => {
  it("stacks fixed-column workspaces and fits the memory controls at tablet widths", () => {
    const tablet = mediaBlocks(900).join("\n");
    expect(tablet).toMatch(/\.view-conversation \.product-home-body\s*\{\s*grid-template-columns:\s*minmax\(0, 1fr\)/);
    expect(tablet).toMatch(/\.operations \.db-settings-overview\s*\{\s*grid-template-columns:\s*minmax\(0, 1fr\)/);
    expect(tablet).toMatch(/\.operations \.op-memory-split\s*\{\s*grid-template-columns:\s*minmax\(0, 1fr\)/);
    expect(tablet).toMatch(/\.operations-memory \.op-toolbar\s*\{\s*flex-wrap:\s*wrap/);
    expect(tablet).toMatch(/\.operations \.db-computer-stage\s*\{\s*grid-template-columns:\s*minmax\(0, 1fr\)/);
  });

  it("keeps Home, prompt suggestions, and practice actions usable on phones", () => {
    const phone = mediaBlocks(640).join("\n");
    expect(phone).toMatch(/\.daybreak-home \.db-next > \.db-primary\s*\{\s*grid-column:\s*1 \/ -1/);
    expect(phone).toMatch(/\.db-prompt-suggestions\s*\{\s*flex-wrap:\s*wrap/);
    expect(phone).toMatch(/\.db-practice-entry-footer\s*\{\s*grid-template-columns:\s*minmax\(0, 1fr\)/);
    expect(mediaBlocks(360).join("\n")).toMatch(/\.daybreak-home \.db-home-context\s*\{\s*grid-template-columns:\s*minmax\(0, 1fr\)/);
  });

  it("keeps learner and project controls visible at narrow phone widths", () => {
    expect(capabilityCss).toMatch(/@media\s*\(max-width:\s*640px\)[\s\S]*?\.db-design-atelier>header\s*\{[^}]*grid-template-columns:\s*minmax\(0,1fr\)/);
    expect(capabilityCss).toMatch(/\.db-capability-controls\s*\{[^}]*display:grid/);
    expect(capabilityCss).toMatch(/\.db-atelier-stages\s*\{[^}]*display:grid/);
    expect(capabilityCss).toMatch(/@media\s*\(max-width:\s*360px\)[\s\S]*?\.db-capability-controls,\.db-atelier-stages\s*\{[^}]*grid-template-columns:minmax\(0,1fr\)/);
  });

  it("disables app animation and smooth scrolling for reduced-motion users", () => {
    expect(daybreakCss).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)[\s\S]*?\.daybreak\s+\*[^}]*animation:\s*none!important/);
    expect(daybreakCss).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)[\s\S]*?transition:\s*none!important/);
    expect(daybreakCss).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)[\s\S]*?scroll-behavior:\s*auto!important/);
  });
});
