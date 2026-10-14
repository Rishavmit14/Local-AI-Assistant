// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Modal } from "./Modal";
import { getModalFocusableElements } from "./modalFocus";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

describe("workspace modal keyboard behavior", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;

  afterEach(() => {
    act(() => root?.unmount());
    container?.remove();
    root = undefined;
    container = undefined;
    vi.restoreAllMocks();
  });

  it("traps focus around visible controls and returns focus when closed", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Search and Browse";
    document.body.append(trigger);
    trigger.focus();
    vi.spyOn(HTMLElement.prototype, "getClientRects").mockReturnValue([{ width: 1, height: 1 } as DOMRect] as unknown as DOMRectList);

    const onClose = vi.fn();
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const content = createElement("div", null,
      createElement("input", { "aria-label": "Search workspaces" }),
      createElement("button", null, "Close"),
      createElement("details", null,
        createElement("summary", null, "More destinations"),
        createElement("button", null, "Hidden destination"),
      ),
    );
    act(() => root?.render(createElement(Modal, { label: "Workspace search", onClose, children: content })));

    const input = container.querySelector("input")!;
    const summary = container.querySelector("summary")!;
    const collapsedItem = container.querySelector<HTMLButtonElement>("details button")!;
    const dialog = container.querySelector<HTMLElement>("[role=dialog]")!;
    expect(document.activeElement).toBe(input);
    expect(getModalFocusableElements(dialog)).toEqual([input, container.querySelector("button"), summary]);
    expect(getModalFocusableElements(dialog)).not.toContain(collapsedItem);

    const forward = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
    act(() => { summary.focus(); summary.dispatchEvent(forward); });
    expect(forward.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(input);

    const reverse = new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true });
    act(() => input.dispatchEvent(reverse));
    expect(reverse.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(summary);

    collapsedItem.focus();
    const escapedForward = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
    act(() => collapsedItem.dispatchEvent(escapedForward));
    expect(escapedForward.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(input);

    const externallyFocused = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
    act(() => { trigger.focus(); trigger.dispatchEvent(externallyFocused); });
    expect(externallyFocused.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(input);

    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })));
    expect(onClose).toHaveBeenCalledOnce();
    act(() => root?.unmount());
    root = undefined;
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});
