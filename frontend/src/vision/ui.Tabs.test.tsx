// @vitest-environment jsdom
import { act, createElement, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { Tabs } from "./ui";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

describe("workspace tabs keyboard behavior", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;

  afterEach(() => {
    act(() => root?.unmount());
    root = undefined;
    container?.remove();
  });

  it("moves selection and focus with arrows, Home, and End", async () => {
    function ControlledTabs() {
      const [value, setValue] = useState("all");
      return <Tabs label="Review filters" value={value} onChange={setValue} items={[
        { id: "all", label: "All" }, { id: "new", label: "New" }, { id: "seen", label: "Seen" },
      ]} />;
    }
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => { root?.render(createElement(ControlledTabs)); });
    const tabs = [...container.querySelectorAll<HTMLButtonElement>("[role=tab]")];
    expect(tabs[0].tabIndex).toBe(0);
    expect(tabs.slice(1).every((tab) => tab.tabIndex === -1)).toBe(true);

    await act(async () => { tabs[0].focus(); tabs[0].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); });
    expect(document.activeElement).toBe(tabs[1]);
    expect(tabs[1].getAttribute("aria-selected")).toBe("true");
    expect(tabs[1].tabIndex).toBe(0);

    await act(async () => { tabs[1].dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true })); });
    expect(document.activeElement).toBe(tabs[2]);
    expect(tabs[2].getAttribute("aria-selected")).toBe("true");

    await act(async () => { tabs[2].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); });
    expect(document.activeElement).toBe(tabs[0]);
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
  });
});
