/**
 * 推荐商品卡片（N4 重构）
 * 商品图、价格区、核心指标、匹配/风险标签、理由 bullets、CTA 区
 */
import {
  AlertTriangle,
  BarChart2,
  BookOpenCheck,
  Check,
  MessageSquarePlus,
  Scale,
  Star,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "../lib/format";
import type { RecommendedProduct } from "../types/shopping";

type ProductCardProps = {
  product: RecommendedProduct;
  onFeedback?: (feedbackType: string, productId: string) => void;
  onProductClick?: (productId: string, action: string) => void;
  onDetail?: (productId: string) => void;
  onCompare?: (productId: string) => void;
  onAsk?: (productId: string, title: string) => void;
  inCompare?: boolean;
};

const VERDICT_STYLE: Record<string, string> = {
  最推荐: "bg-primary/10 text-primary",
  预算优先: "bg-price/10 text-price",
  品质优先: "bg-good/10 text-good",
  谨慎购买: "bg-risk/10 text-risk",
};

export function ProductCard({
  product,
  onFeedback,
  onProductClick,
  onDetail,
  onCompare,
  onAsk,
  inCompare,
}: ProductCardProps) {
  const price = product.promotion_price ?? product.price;
  const hasPromo = product.promotion_price != null && product.promotion_price < product.price;
  const savePct = hasPromo
    ? Math.round((1 - (product.promotion_price ?? 0) / product.price) * 100)
    : 0;
  const riskTags = extractRiskTags(product.reason);
  const bullets = splitReasonBullets(product.reason);
  const hotSales = (product.sales_30d ?? 0) >= 200;
  const lowSample = (product.review_count ?? 0) > 0 && (product.review_count ?? 0) < 10;

  // N10.1 商品曝光埋点：卡片进入视口时上报一次
  const rootRef = useRef<HTMLElement | null>(null);
  const [impressionSent, setImpressionSent] = useState(false);
  useEffect(() => {
    const node = rootRef.current;
    if (!node || impressionSent) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          onProductClick?.(product.product_id, "impression");
          setImpressionSent(true);
          observer.disconnect();
        }
      },
      { threshold: 0.5 },
    );
    observer.observe(node);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product.product_id, impressionSent]);

  const track = (action: string) => onProductClick?.(product.product_id, action);

  return (
    <article
      ref={rootRef}
      className="flex gap-4 rounded-xl2 border border-line bg-white p-4 shadow-card transition hover:border-primary/40"
    >
      {/* 商品图（N4.1）：主图缺失时用品类色块占位 */}
      <div className="grid h-24 w-24 shrink-0 place-items-center overflow-hidden rounded-lg bg-gradient-to-br from-primary/10 to-primary/5">
        <ShoppingGlyph category={product.category_name} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="mb-1 flex flex-wrap items-center gap-1.5">
              {product.verdict && (
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[11px] font-semibold",
                    VERDICT_STYLE[product.verdict] ?? "bg-subtle text-ink/70",
                  )}
                >
                  {product.verdict}
                </span>
              )}
              {product.budget_exceeded && (
                <span className="rounded bg-risk/10 px-1.5 py-0.5 text-[11px] text-risk">
                  略超预算
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={() => {
                track("view");
                onDetail?.(product.product_id);
              }}
              className="line-clamp-2 text-left text-sm font-semibold leading-5 text-ink transition hover:text-primary"
            >
              {product.title}
            </button>
          </div>
          {/* 价格区（N4.2） */}
          <div className="shrink-0 text-right">
            <div className="text-lg font-bold leading-6 text-price">¥{price}</div>
            {hasPromo && (
              <div className="text-[11px] leading-4 text-ink/40">
                <span className="mr-1 line-through">¥{product.price}</span>
                <span className="rounded bg-price/10 px-1 text-price">省{savePct}%</span>
              </div>
            )}
          </div>
        </div>

        {/* 核心指标（N4.3） */}
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink/55">
          <span className="inline-flex items-center gap-0.5">
            <Star className="h-3 w-3 fill-brass text-brass" aria-hidden="true" />
            <span className="font-semibold text-ink/80">{product.rating}</span>
          </span>
          {(product.sales_30d ?? 0) > 0 && <span>月销 {product.sales_30d}</span>}
          {hotSales && (
            <span className="rounded bg-brass/10 px-1 text-brass">热销</span>
          )}
          {lowSample && (
            <span className="rounded bg-subtle px-1 text-ink/45">评价样本较少</span>
          )}
        </div>

        {/* 风险标签（N4.5） */}
        {riskTags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {riskTags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-0.5 rounded bg-risk/8 px-1.5 py-0.5 text-[11px] text-risk/90"
              >
                <AlertTriangle className="h-2.5 w-2.5" aria-hidden="true" />
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* 推荐理由 bullets（N4.6） */}
        {bullets.length > 0 && (
          <ul className="mt-2 space-y-1">
            {bullets.map((bullet, index) => (
              <li key={index} className="flex items-start gap-1.5 text-xs leading-5 text-ink/75">
                <Check className="mt-1 h-3 w-3 shrink-0 text-good" aria-hidden="true" />
                <span className="min-w-0">{bullet}</span>
              </li>
            ))}
          </ul>
        )}

        {/* CTA 区（N4.7） */}
        <div className="mt-3 flex items-center gap-2 border-t border-line pt-2.5">
          <button
            type="button"
            onClick={() => {
              track("detail");
              onDetail?.(product.product_id);
            }}
            className="inline-flex items-center gap-1 rounded-md border border-line px-2.5 py-1 text-xs font-medium text-ink/70 transition hover:border-primary/40 hover:text-primary"
          >
            <BookOpenCheck className="h-3 w-3" aria-hidden="true" />
            查看详情
          </button>
          <button
            type="button"
            onClick={() => {
              track("compare");
              onCompare?.(product.product_id);
            }}
            disabled={inCompare}
            className={cn(
              "inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-45",
              inCompare
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-line text-ink/70 hover:border-primary/40 hover:text-primary",
            )}
          >
            <Scale className="h-3 w-3" aria-hidden="true" />
            {inCompare ? "已加入对比" : "加入对比"}
          </button>
          <button
            type="button"
            onClick={() => {
              track("ask");
              onAsk?.(product.product_id, product.title);
            }}
            className="inline-flex items-center gap-1 rounded-md border border-line px-2.5 py-1 text-xs font-medium text-ink/70 transition hover:border-primary/40 hover:text-primary"
          >
            <MessageSquarePlus className="h-3 w-3" aria-hidden="true" />
            继续追问
          </button>
          <span className="mx-1 h-4 w-px bg-line" />
          <FeedbackInline onFeedback={(type) => onFeedback?.(type, product.product_id)} />
        </div>
      </div>
    </article>
  );
}

function FeedbackInline({ onFeedback }: { onFeedback: (type: string) => void }) {
  const [done, setDone] = useState(false);
  const [open, setOpen] = useState(false);

  if (done) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-good">
        <Check className="h-3 w-3" aria-hidden="true" />
        感谢反馈
      </span>
    );
  }

  return open ? (
    <div className="flex flex-wrap items-center gap-1">
      {[
        ["helpful", "准确"],
        ["too_expensive", "太贵"],
        ["too_few", "太少"],
        ["not_accurate", "理由不可信"],
        ["not_understand", "没懂"],
        ["out_of_stock", "无货"],
      ].map(([value, label]) => (
        <button
          key={value}
          type="button"
          onClick={() => {
            onFeedback(value);
            setDone(true);
          }}
          className="rounded border border-line px-1.5 py-0.5 text-[11px] text-ink/60 transition hover:border-primary/40 hover:text-primary"
        >
          {label}
        </button>
      ))}
    </div>
  ) : (
    <button
      type="button"
      onClick={() => setOpen(true)}
      className="inline-flex items-center gap-1 text-xs text-ink/55 transition hover:text-ink"
    >
      <BarChart2 className="h-3 w-3" aria-hidden="true" />
      反馈
    </button>
  );
}

function ShoppingGlyph({ category }: { category: string }) {
  const label = category.slice(0, 2);
  return (
    <div className="grid place-items-center text-primary/60">
      <ShoppingBagIcon />
      <span className="mt-1 text-[11px] font-medium">{label}</span>
    </div>
  );
}

function ShoppingBagIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M6 7h12l1 13H5L6 7z" strokeLinejoin="round" />
      <path d="M9 10V6a3 3 0 0 1 6 0v4" strokeLinecap="round" />
    </svg>
  );
}

/** 推荐理由拆成 ≤3 条 bullet */
function splitReasonBullets(reason: string): string[] {
  const parts = reason
    .split(/[。；;！!]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 3 && !item.startsWith("需要注意"));
  return parts.slice(0, 3);
}

/** 从理由中提取风险标签（短语级） */
function extractRiskTags(reason: string): string[] {
  const markers = ["需要注意的是", "风险", "但差评", "需谨慎"];
  for (const marker of markers) {
    const index = reason.indexOf(marker);
    if (index > 0) {
      const tail = reason
        .slice(index)
        .split(/[。；;]/)
        .map((item) => item.trim())
        .filter(Boolean);
      return tail.slice(0, 2);
    }
  }
  return [];
}
