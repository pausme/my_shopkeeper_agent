/**
 * 抽屉可访问性 Hook（N12.16/N12.17/N12.27）
 * 统一首焦点进入、Esc 关闭、Tab 焦点循环、关闭后焦点返回触发元素。
 * 嵌套抽屉（详情 → 搭配购）经模块级栈管理：只有最上层响应 Esc/Tab，
 * 关闭上层后焦点回到仍在挂载的下层入口。
 * 用法：const { panelRef, closeRef, handleClose } = useDrawerFocus(open, onClose);
 */
import { useCallback, useEffect, useRef } from "react";

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

// 模块级抽屉栈：记录当前打开的抽屉实例（嵌套时后进者在上层）
const drawerStack: unknown[] = [];

export function useDrawerFocus(open: boolean, onClose: () => void) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const triggerRef = useRef<Element | null>(null);
  const instanceRef = useRef({});
  // StrictMode（dev）会 mount→cleanup→mount 双跑 effect：同一次打开只捕获
  // 一次触发元素，第二次运行不得把 triggerRef 覆盖成自己的关闭按钮
  const capturedRef = useRef(false);
  // N12.27：onClose 经 ref 持有（调用方多为内联箭头函数，身份不稳定），
  // 保证 handleClose 与键盘 effect 只随 open 变化——否则 App 每次重渲染都会
  // 重跑 effect 并把焦点抢回关闭按钮
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // N12.16：所有关闭路径（Esc/遮罩/按钮）都经 handleClose 恢复触发元素焦点
  const handleClose = useCallback(() => {
    (triggerRef.current as HTMLElement | null)?.focus?.();
    onCloseRef.current();
  }, []);

  useEffect(() => {
    if (!open) {
      capturedRef.current = false;
      return;
    }
    if (!capturedRef.current) {
      triggerRef.current = document.activeElement;
      capturedRef.current = true;
    }
    closeRef.current?.focus();
    drawerStack.push(instanceRef.current);
    const isTop = () => drawerStack[drawerStack.length - 1] === instanceRef.current;
    const onKey = (event: KeyboardEvent) => {
      // N12.27：嵌套时只有最上层抽屉响应键盘，避免 Esc 连环关闭
      if (!isTop()) return;
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
    return () => {
      window.removeEventListener("keydown", onKey);
      const index = drawerStack.indexOf(instanceRef.current);
      if (index !== -1) drawerStack.splice(index, 1);
    };
  }, [open, handleClose]);

  return { panelRef, closeRef, handleClose };
}
