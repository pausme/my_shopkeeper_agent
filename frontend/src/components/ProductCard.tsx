/**
 * 推荐商品卡片
 * 展示价格/评分/销量/推荐理由与风险提示，附轻反馈入口
 */
import { AlertTriangle, Star, ThumbsUp } from "lucide-react";
import { cn } from "../lib/format";
import type { RecommendedProduct } from "../types/shopping";

type ProductCardProps = {
  product: RecommendedProduct;
  onFeedback?: (feedbackType: string, productId: string) => void;
  /** 商品点击上报（M8.3 埋点） */
  onProductClick?: (productId: string) => void;
};

export function ProductCard({ product, onFeedback, onProductClick }: ProductCardProps) {
  const price = product.promotion_price ?? product.price;
  const hasPromo = product.promotion_price != null && product.promotion_price < product.price;
  // 从推荐理由中拆出风险提示（模型被要求在理由里带出风险）
  const riskHint = extractRiskHint(product.reason);

  return (
    <article className="border border-ink/10 bg-white/75 p-4 shadow-line transition hover:border-moss/30">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {product.verdict && (
            <span
              className={cn(
                "mb-1.5 inline-block px-2 py-0.5 text-[11px] font-semibold",
                product.verdict === "谨慎购买"
                  ? "bg-tomato/15 text-tomato"
                  : product.verdict === "预算优先"
                    ? "bg-brass/20 text-brass"
                    : "bg-moss/15 text-moss",
              )}
            >
              {product.verdict}
            </span>
          )}
          {product.budget_exceeded && (
            <div className="mb-1 text-[11px] text-tomato/80">* 略超预算，但综合优势明显</div>
          )}
          <button
            type="button"
            onClick={() => onProductClick?.(product.product_id)}
            className="text-left text-sm font-semibold leading-5 text-ink transition hover:text-moss"
            title="查看商品（已记录点击兴趣）"
          >
            {product.title}
          </button>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-base font-semibold text-ink">¥{price}</div>
          {hasPromo && (
            <div className="text-[11px] text-ink/40 line-through">¥{product.price}</div>
          )}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink/55">
        <span className="inline-flex items-center gap-1">
          <Star className="h-3 w-3 text-brass" aria-hidden="true" />
          {product.rating} 分
        </span>
        {product.sales_30d != null && <span>月销 {product.sales_30d}</span>}
        {product.brand && <span>{product.brand}</span>}
        {Object.entries(product.attributes ?? {})
          .slice(0, 2)
          .map(([key, value]) => (
            <span key={key}>
              {key}: {value}
            </span>
          ))}
      </div>

      {product.reason && (
        <p className="mt-2 border-l-2 border-moss/40 pl-2 text-xs leading-5 text-ink/75">
          <ThumbsUp className="mr-1 inline h-3 w-3 text-moss" aria-hidden="true" />
          {product.reason}
        </p>
      )}

      {riskHint && (
        <p className="mt-1.5 border-l-2 border-tomato/40 pl-2 text-xs leading-5 text-tomato/90">
          <AlertTriangle className="mr-1 inline h-3 w-3" aria-hidden="true" />
          {riskHint}
        </p>
      )}

      {onFeedback && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-ink/5 pt-2">
          <span className="text-[11px] text-ink/40">这条推荐：</span>
          {[
            ["helpful", "推荐准确"],
            ["too_expensive", "价格不合适"],
            ["too_few", "商品太少"],
            ["not_accurate", "理由不可信"],
            ["not_understand", "没理解我的需求"],
            ["out_of_stock", "已经无货"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => onFeedback(value, product.product_id)}
              className={cn(
                "border border-ink/10 px-2 py-0.5 text-[11px] text-ink/55 transition",
                "hover:border-moss/40 hover:text-ink",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}

function extractRiskHint(reason: string): string {
  // 约定：模型在 reason 中以"需要注意的是"或"风险"引出风险段
  const markers = ["需要注意的是", "风险", "但差评", "需谨慎"];
  for (const marker of markers) {
    const index = reason.indexOf(marker);
    if (index > 0) {
      return reason.slice(index);
    }
  }
  return "";
}
