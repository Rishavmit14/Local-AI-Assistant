import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { getModalFocusableElements } from "./modalFocus";

type ModalProps = { label: string; children: ReactNode; onClose: () => void; wide?: boolean };

function useEscape(onClose: () => void) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);
}

export function Modal({ label, children, onClose, wide = false }: ModalProps) {
  const ref = useRef<HTMLDivElement>(null);
  const returnFocus = useRef(document.activeElement as HTMLElement | null);
  useEscape(onClose);

  useEffect(() => {
    const before = returnFocus.current;
    const node = ref.current;
    const focusable = () => getModalFocusableElements(node);
    focusable()[0]?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const all = focusable();
      if (!all.length) return;
      const activeIndex = all.indexOf(document.activeElement as HTMLElement);
      const first = all[0];
      const last = all[all.length - 1];
      if (activeIndex === -1) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && activeIndex === 0) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && activeIndex === all.length - 1) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      before?.focus();
    };
  }, []);

  return <div className="modal-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div ref={ref} className={`modal-surface ${wide ? "modal-wide" : ""}`} role="dialog" aria-modal="true" aria-label={label}>
      {children}
    </div>
  </div>;
}
