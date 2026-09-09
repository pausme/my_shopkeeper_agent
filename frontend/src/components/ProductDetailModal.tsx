/**
 * 商品详情：右侧证据抽屉（N12.7，原中心弹窗改版）
 * 参数、评价摘要、适合人群、风险、样本量与更新时间；
 * Esc/遮罩/关闭按钮可关，焦点进入抽屉并循环，关闭后回到触发元素
 */
import { AlertTriangle, Check, CircleCheckBig, Copy, Scale, ShoppingBag, Star, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { fetchProductSummary, type ProductSummary } from "../lib/shoppingApi";
import type { RecommendedProduct } from "../types/shopping";

type ProductDetailModalProps = {
  product: RecommendedProduct | null;
  onClose: () => void;
  /** findings #21：详情页决策下一步 */
  onCompare?: (productId: string) => void;
  onAsk?: (productId: string, title: string) => void;
  /** S3-5：查看搭配购买方案 */
  onShowBundle?: (productId: string) => void;
  /** N11.31：已购标记（本地维护，用于搭配购买去重） */
  purchased?: boolean;
  onTogglePurchased?: (productId: string) => void;
};

export function ProductDetailModal({
  product,
  onClose,
  onCompare,
  onAsk,
  onShowBundle,
  purchased = false,
  onTogglePurchased,
}: ProductDetailModalProps) {
  const [summary, setSummary] = useState<ProductSummary | null>(null);
  const [error, setError] = useState("");
  const panelRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  // N12.7：关闭后焦点回到触发元素
  const triggerRef = useRef<Element | null>(null);

  useEffect(() => {
    if (!product) return;
    setSummary(null);
    setError("");
    triggerRef.current = document.activeElement;
    fetchProductSummary(product.product_id)
      .then(setSummary)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [product]);

  // findings #23/N12.7：Esc 关闭 + Tab 焦点循环在抽屉内
  useEffect(() => {
    if (!product) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusables = panelRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
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
    closeRef.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [product, onClose]);

  // N12.7：关闭时焦点返回触发元素
  const handleClose = () => {
    (triggerRef.current as HTMLElement | null)?.focus?.();
    onClose();
  };

  if (!product) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm"
      onClick={handleClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${product.title} 的证据详情`}
    >
      {/* N12.7 右侧证据抽屉：保持当前会话上下文可见 */}
      <div
        ref={panelRef}
        onClick={(event) => event.stopPropagation()}
        className="drawer-panel absolute right-0 top-0 flex h-full w-full max-w-[480px] flex-col bg-white shadow-drawer"
      >
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="mb-1 flex flex-wrap items-center gap-3 text-xs text-ink/55">
                <span className="inline-flex items-center gap-0.5">
                  <Star className="h-3 w-3 fill-brass text-brass" aria-hidden="true" />
                  <span className="font-semibold tabular-nums text-ink/80">{product.rating}</span>
                </span>
                <span className="text-[15px] font-bold tabular-nums text-price">
                  ¥{product.promotion_price ?? product.price}
                </span>
                {product.brand && <span>{product.brand}</span>}
                {/* N6.2/P1 图文摘要增强：风险等级徽章 + 更新时间 */}
                {summary?.risk.level && summary.risk.level !== "unknown" && (
                  <span
                    className={
                      summary.risk.level === "high"
                        ? "rounded bg-risk/10 px-1.5 py-0.5 text-risk"
                        : summary.risk.level === "medium"
                          ? "rounded bg-warning/15 px-1.5 py-0.5 text-warning"
                          : "rounded bg-good/10 px-1.5 py-0.5 text-good"
                    }
                  >
                    风险{summary.risk.level === "high" ? "高" : summary.risk.level === "medium" ? "中" : "低"}
                  </span>
                )}
              </div>
              <h3 className="text-base font-semibold leading-6 text-ink">{product.title}</h3>
              {/* 数据可信信息（findings #22 / N12.7 价格来源） */}
              <div className="mt-1.5 flex flex-wrap gap-2 text-[11px] text-ink/40">
                <span className="rounded bg-subtle px-1.5 py-0.5">演示数据</span>
                {summary?.updated_at && <span>数据更新于 {summary.updated_at}</span>}
                {(summary?.risk.sample_size ?? 0) > 0 && (
                  <span className="tabular-nums">评价样本 {summary!.risk.sample_size} 条</span>
                )}
                <span>价格来源：演示商品库</span>
              </div>
            </div>
            <button
              ref={closeRef}
              type="button"
              onClick={handleClose}
              aria-label="关闭详情"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-ink/45 transition hover:bg-soft hover:text-ink active:scale-[0.98]"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>

          {error && (
            <div className="rounded-lg bg-risk/5 px-3 py-2 text-sm leading-5 text-risk">
              商品详情暂时加载失败，推荐卡中的信息仍可查看。
              <button
                type="button"
                className="ml-1 underline underline-offset-2"
                onClick={() => {
                  setError("");
                  fetchProductSummary(product.product_id)
                    .then(setSummary)
                    .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
                }}
              >
                重新加载
              </button>
            </div>
          )}

          {!summary && !error && (
            <div className="space-y-3" aria-label="正在加载评价摘要">
              {[0, 1, 2].map((index) => (
                <div key={index} className="shimmer h-16 rounded-lg" />
              ))}
            </div>
          )}

          {summary && (
            <div className="space-y-4">
              {/* 核心参数（N6.4：缺失参数显示暂无数据） */}
              <Section title="核心参数">
                <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
                  {Object.entries(summary.attributes ?? {}).length > 0 ? (
                    Object.entries(summary.attributes).map(([key, value]) => (
                      <div key={key} className="flex justify-between gap-2">
                        <span className="text-ink/50">{key}</span>
                        <span className="text-right font-medium text-ink/80">{value || "暂无数据"}</span>
                      </div>
                    ))
                  ) : (
                    <span className="text-ink/45">暂无参数数据</span>
                  )}
                </div>
              </Section>

              {/* 评价摘要（N6.2） */}
              <Section title="评价摘要">
                {summary.risk.sample_size > 0 ? (
                  <div className="space-y-2.5 text-xs leading-5">
                    {summary.risk.positive_summary && (
                      <div>
                        <div className="mb-1 flex items-center gap-1 font-semibold text-good">
                          <Check className="h-3 w-3" aria-hidden="true" />
                          好评要点（<span className="tabular-nums">{summary.risk.sample_size}</span> 条评价）
                        </div>
                        <p className="text-ink/70">{summary.risk.positive_summary}</p>
                      </div>
                    )}
                    {summary.risk.summary && (
                      <div>
                        <div className="mb-1 flex items-center gap-1 font-semibold text-risk">
                          <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                          差评与风险
                        </div>
                        <p className="text-ink/70">{summary.risk.summary}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="rounded-lg bg-subtle px-3 py-2 text-xs text-ink/55">
                    当前评价样本不足，暂无可靠的口碑摘要，建议参考参数与其他渠道信息。
                  </div>
                )}
              </Section>

              {/* 适合 / 不适合 */}
              <div className="grid gap-3">
                {summary.risk.suitable_for && (
                  <Section title="适合人群">
                    <p className="text-xs leading-5 text-ink/70">{summary.risk.suitable_for}</p>
                  </Section>
                )}
                {summary.risk.not_suitable_for && (
                  <Section title="不建议购买">
                    <p className="text-xs leading-5 text-risk/85">{summary.risk.not_suitable_for}</p>
                  </Section>
                )}
              </div>
            </div>
          )}
        </div>

        {/* findings #21/N12.7：底部固定操作区 */}
        <div className="flex shrink-0 flex-wrap items-center gap-2 border-t border-line bg-white px-6 py-3.5">
          <button
            type="button"
            onClick={() => onCompare?.(product.product_id)}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-primary/45 px-3 text-xs font-medium text-primary transition hover:bg-primary-soft active:scale-[0.98]"
          >
            <Scale className="h-3.5 w-3.5" aria-hidden="true" />
            加入对比
          </button>
          <button
            type="button"
            onClick={() => {
              navigator.clipboard?.writeText(product.title);
            }}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-line px-3 text-xs text-ink/60 transition hover:border-primary/40 hover:text-primary active:scale-[0.98]"
          >
            <Copy className="h-3.5 w-3.5" aria-hidden="true" />
            复制名称
          </button>
          {onShowBundle && (
            <button
              type="button"
              onClick={() => onShowBundle(product.product_id)}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-line px-3 text-xs text-ink/60 transition hover:border-primary/40 hover:text-primary active:scale-[0.98]"
            >
              <ShoppingBag className="h-3.5 w-3.5" aria-hidden="true" />
              查看搭配购
            </button>
          )}
          {onTogglePurchased && (
            <button
              type="button"
              onClick={() => onTogglePurchased(product.product_id)}
              title="已购商品不会出现在搭配购买建议里"
              className={
                purchased
                  ? "inline-flex h-9 items-center gap-1.5 rounded-lg bg-good/10 px-3 text-xs font-medium text-good transition hover:bg-good/20 active:scale-[0.98]"
                  : "inline-flex h-9 items-center gap-1.5 rounded-lg border border-line px-3 text-xs text-ink/60 transition hover:border-primary/40 hover:text-primary active:scale-[0.98]"
              }
            >
              {purchased ? (
                <>
                  <CircleCheckBig className="h-3.5 w-3.5" aria-hidden="true" />
                  已购（点击撤销）
                </>
              ) : (
                <>
                  <ShoppingBag className="h-3.5 w-3.5" aria-hidden="true" />
                  标记为已购
                </>
              )}
            </button>
          )}
          {onAsk && (
            <button
              type="button"
              onClick={() => {
                onAsk(product.product_id, product.title);
                handleClose();
              }}
              className="ml-auto text-xs font-medium text-primary underline-offset-2 transition hover:underline"
            >
              继续追问这款 →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-2 text-sm font-semibold text-ink">{title}</div>
      {children}
    </div>
  );
}
