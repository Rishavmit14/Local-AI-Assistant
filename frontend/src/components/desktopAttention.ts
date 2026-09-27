import type { FridayDesktopAction } from "../runtime";

export function pendingDesktopActionCount(actions: FridayDesktopAction[]): number {
  return actions.filter((action) => action.state === "proposed" || action.state === "approved").length;
}
