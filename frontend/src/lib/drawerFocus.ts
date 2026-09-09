/**
 * 抽屉可访问性 Hook（N12.16/N12.17）
 * 统一首焦点进入、Esc 关闭、Tab 焦点循环、关闭后焦点返回触发元素。
 * 用法：const { panelRef, closeRef, handleClose } = useDrawerFocus(open, onClose);
 */
import { useCallback, useEffect, useRef } from "react";

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function useDrawerFocus(open: boolean, onClose: () => void) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const triggerRef = useRef<Element | null>(null);

  // N12.16：所有关闭路径（Esc/遮罩/按钮）都经 handleClose 恢复触发元素焦点
  const handleClose = useCallback(() => {
    (triggerRef.current as HTMLElement | null)?.focus?.();
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    triggerRef.current = document.activeElement;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        handleClose();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusables = panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, handleClose]);

  return { panelRef, closeRef, handleClose };
}
