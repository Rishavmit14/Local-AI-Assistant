export function getModalFocusableElements(node: HTMLElement | null) {
  return [...(node?.querySelectorAll<HTMLElement>(
    'a[href],button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),summary,[tabindex]:not([tabindex="-1"])',
  ) ?? [])].filter((element) => {
    const closedDisclosure = element.closest("details:not([open])");
    const disclosureSummary = closedDisclosure !== null
      && element.matches("summary")
      && element.parentElement === closedDisclosure;
    return (!closedDisclosure || disclosureSummary)
      && element.getClientRects().length > 0
      && getComputedStyle(element).visibility !== "hidden";
  });
}
