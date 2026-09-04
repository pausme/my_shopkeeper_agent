/**
 * 商品详情弹窗（N6.2/N6.5）
 * 展示商品参数、好评/差评摘要、适合/不适合人群、样本量与风险等级
 */
import { AlertTriangle, Check, Star, X } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchProductSummary, type ProductSummary } from "../lib/shoppingApi";
import type { RecommendedProduct } from "../types/shopping";

type ProductDetailModalProps = {
  product: RecommendedProduct | null;
  onClose: () => void;
};

export function ProductDetailModal({ product, onClose }: ProductDetailModalProps) {
  const [summary, setSummary] = useState<ProductSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!product) return;
    setSummary(null);
    setError("");
    fetchProductSummary(product.product_id)
      .then(setSummary)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [product]);

  if (!product) return null;

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-label="商品详情"
    >
      <div
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl2 bg-white p-6 shadow-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-ink">{product.title}</h3>
            <div className="mt-1 flex items-center gap-3 text-xs text-ink/55">
              <span className="inline-flex items-center gap-0.5">
                <Star className="h-3 w-3 fill-brass text-brass" aria-hidden="true" />
                {product.rating}
              </span>
              <span className="text-price font-semibold">¥{product.promotion_price ?? product.price}</span>
              {product.brand && <span>{product.brand}</span>}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-ink/45 transition hover:bg-subtle hover:text-ink"
            aria-label="关闭"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {error && (
          <div className="rounded-lg bg-risk/10 px-3 py-2 text-sm text-risk">{error}</div>
        )}

        {!summary && !error && (
          <div className="space-y-3">
            {[0, 1, 2].map((index) => (
              <div key={index} className="shimmer h-16 rounded-lg" />
            ))}
          </div>
        )}

        {summary && (
          <div className="space-y-4">
            {/* 核心参数（N6.4：缺失参数显示暂无数据） */}
            <Section title="核心参数">
              <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs sm:grid-cols-3">
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
                        好评要点（{summary.risk.sample_size} 条评价）
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
            <div className="grid gap-3 sm:grid-cols-2">
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
