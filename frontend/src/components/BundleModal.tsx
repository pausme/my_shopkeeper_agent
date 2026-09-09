/**
 * 搭配购买弹窗（二期 P1）
 * 主商品 + 组合购/补充购/替代购分组展示
 */
import { Loader2, ShoppingBag, X } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchBundleRecommend } from "../lib/shoppingApi";
import type { RecommendedProduct } from "../types/shopping";

type BundleGroup = {
  type: string;
  reason: string;
  products: Array<{
    product_id: string;
    title: string;
    price: number;
    promotion_price: number | null;
    rating: number;
    reason: string;
  }>;
};

type BundleModalProps = {
  product: RecommendedProduct;
  /** N11.31：已购商品 id——服务端从搭配结果中剔除，前端提示已排除 */
  purchasedProductIds?: string[];
  /** N11.30：埋点归属会话 */
  sessionId?: string;
  onClose: () => void;
  onFollowUp?: (question: string) => void;
};

const GROUP_BADGE: Record<string, string> = {
  组合购: "bg-primary/10 text-primary",
  补充购: "bg-brass/10 text-brass",
  替代购: "bg-subtle text-ink/60",
};

export function BundleModal({
  product,
  purchasedProductIds = [],
  sessionId,
  onClose,
  onFollowUp,
}: BundleModalProps) {
  const [bundles, setBundles] = useState<BundleGroup[] | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    fetchBundleRecommend(product.product_id, purchasedProductIds, sessionId)
      .then((d) => {
        setBundles(d.bundles ?? []);
        setNote(d.note ?? "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
    return () => window.removeEventListener("keydown", onKey);
  }, [product.product_id, purchasedProductIds, sessionId, onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="搭配购买方案"
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      {/* N12.10 搭配方案抽屉：右侧打开，保持会话上下文 */}
      <div
        className="drawer-panel absolute right-0 top-0 h-full w-full max-w-[440px] overflow-y-auto rounded-l-xl3 bg-white px-6 py-5 shadow-drawer"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="inline-flex items-center gap-1.5 text-base font-semibold text-ink">
              <ShoppingBag className="h-4 w-4 text-primary" aria-hidden="true" />
              搭配购买方案
            </h3>
            <p className="mt-1 text-xs text-ink/50">围绕「{product.title}」的组合与补充建议</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-ink/45 transition hover:bg-soft hover:text-ink active:scale-[0.98]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {error && (
          <div className="rounded-lg bg-risk/5 px-3 py-2 text-sm text-risk">{error}</div>
        )}
        {purchasedProductIds.length > 0 && !error && (
          <p className="mb-3 text-xs text-ink/50">
            已自动排除你标记为已购的 {purchasedProductIds.length} 件商品，不再重复推荐。
          </p>
        )}
        {note && <p className="mb-3 text-xs text-brass">{note}</p>}
        {!error && bundles === null && (
          <div className="flex items-center gap-2 py-8 text-sm text-ink/50">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            正在生成搭配方案...
          </div>
        )}
        {bundles && bundles.length === 0 && (
          <p className="py-8 text-center text-sm text-ink/45">
            暂无搭配建议——当前品类单品已足够。
          </p>
        )}

        <div className="space-y-4">
          {bundles?.map((group) => (
            <div key={group.type}>
              <div className="mb-2 flex items-center gap-2">
                <span
                  className={`rounded px-2 py-0.5 text-xs font-semibold ${
                    GROUP_BADGE[group.type] ?? "bg-subtle text-ink/60"
                  }`}
                >
                  {group.type}
                </span>
                <span className="text-xs text-ink/50">{group.reason}</span>
              </div>
              <div className="space-y-2">
                {group.products.map((item) => (
                  <div
                    key={item.product_id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-line px-3 py-2.5"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-ink">{item.title}</div>
                      <div className="text-[11px] text-ink/50">{item.reason}</div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-sm font-bold text-price">
                        ¥{item.promotion_price ?? item.price}
                      </div>
                      <div className="text-[11px] text-ink/45">评分 {item.rating}</div>
                    </div>
                  </div>
                ))}
              </div>
              {onFollowUp && (
                <button
                  type="button"
                  onClick={() => {
                    const names = group.products.map((p) => p.title.slice(0, 12)).join("和");
                    onFollowUp(`${names}和${product.title}搭配买合适吗？`);
                    onClose();
                  }}
                  className="mt-2 text-xs text-primary transition hover:underline"
                >
                  就这个组合，继续问我 →
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
