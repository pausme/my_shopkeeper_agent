/**
 * 桌面筛选面板（N8.3）
 * 作用于最新一次推荐的候选商品：预算上限/品牌排除/最低评分/仅看有货/排除中高风险；
 * 支持一键"按条件重新推荐"（把筛选条件拼成新一轮导购请求）
 */
import { RotateCcw, SlidersHorizontal, X } from "lucide-react";
import { cn } from "../lib/format";
import type { RecommendedProduct } from "../types/shopping";

export type ResultFilters = {
  budgetMax: number | null;
  excludedBrands: string[];
  minRating: number;
  inStockOnly: boolean;
  excludeRisky: boolean;
};

export const EMPTY_FILTERS: ResultFilters = {
  budgetMax: null,
  excludedBrands: [],
  minRating: 0,
  inStockOnly: false,
  excludeRisky: false,
};

export function applyFilters(
  products: RecommendedProduct[],
  filters: ResultFilters,
): RecommendedProduct[] {
  return products.filter((product) => {
    const price = product.promotion_price ?? product.price;
    if (filters.budgetMax != null && price > filters.budgetMax) return false;
    if (filters.excludedBrands.includes(product.brand ?? "")) return false;
    if (filters.minRating > 0 && product.rating < filters.minRating) return false;
    if (filters.inStockOnly && (product.sales_30d ?? 0) <= 0) return false;
    if (filters.excludeRisky && product.verdict === "谨慎购买") return false;
    return true;
  });
}

/** 把筛选条件拼成自然语言追问（走完整导购链路重新推荐） */
export function filtersToQuery(
  filters: ResultFilters,
  baseQuery: string,
): string {
  const parts: string[] = [baseQuery];
  if (filters.budgetMax != null) parts.push(`预算 ${filters.budgetMax} 以内`);
  for (const brand of filters.excludedBrands) parts.push(`不要${brand}`);
  if (filters.minRating >= 4.5) parts.push("评分 4.5 以上");
  if (filters.inStockOnly) parts.push("只要现货");
  return parts.join("，");
}

type FilterPanelProps = {
  open: boolean;
  onClose: () => void;
  products: RecommendedProduct[];
  filters: ResultFilters;
  onChange: (filters: ResultFilters) => void;
  onRequery: (query: string) => void;
  baseQuery: string;
  /** N10.3 埋点回调（App 提供真实 session），未传时静默 */
  onTrack?: (action: string, data: Record<string, string>) => void;
};

export function FilterPanel({
  open,
  onClose,
  products,
  filters,
  onChange,
  onRequery,
  baseQuery,
  onTrack,
}: FilterPanelProps) {
  if (!open) return null;

  const brands = [...new Set(products.map((p) => p.brand).filter(Boolean))] as string[];
  const priceCeiling = Math.ceil(Math.max(...products.map((p) => p.promotion_price ?? p.price), 0));

  const toggleBrand = (brand: string) => {
    onChange({
      ...filters,
      excludedBrands: filters.excludedBrands.includes(brand)
        ? filters.excludedBrands.filter((b) => b !== brand)
        : [...filters.excludedBrands, brand],
    });
  };

  return (
    <aside className="absolute right-4 top-16 z-30 w-72 rounded-xl2 border border-line bg-white p-4 shadow-panel">
      <div className="mb-3 flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink">
          <SlidersHorizontal className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
          筛选本次推荐
        </span>
        <button
          type="button"
          onClick={onClose}
          className="text-ink/40 transition hover:text-ink"
          aria-label="关闭筛选"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>

      {/* 预算上限 */}
      <div className="mb-3">
        <div className="mb-1 flex items-center justify-between text-xs text-ink/60">
          <span>预算上限</span>
          <span className="font-semibold text-price">
            {filters.budgetMax == null ? "不限" : `¥${filters.budgetMax}`}
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={Math.max(priceCeiling, 100)}
          step={10}
          value={filters.budgetMax ?? Math.max(priceCeiling, 100)}
          onChange={(event) => {
            const value = Number(event.target.value);
            onChange({ ...filters, budgetMax: value >= Math.max(priceCeiling, 100) ? null : value });
          }}
          className="w-full accent-primary"
        />
      </div>

      {/* 品牌排除 */}
      {brands.length > 1 && (
        <div className="mb-3">
          <div className="mb-1 text-xs text-ink/60">排除品牌</div>
          <div className="flex flex-wrap gap-1.5">
            {brands.map((brand) => (
              <button
                key={brand}
                type="button"
                onClick={() => toggleBrand(brand)}
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[11px] transition",
                  filters.excludedBrands.includes(brand)
                    ? "border-risk/40 bg-risk/10 text-risk line-through"
                    : "border-line text-ink/60 hover:border-primary/40 hover:text-primary",
                )}
              >
                {brand}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 最低评分 */}
      <div className="mb-3">
        <div className="mb-1 text-xs text-ink/60">最低评分</div>
        <div className="flex gap-1.5">
          {[0, 4.2, 4.5, 4.7].map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => onChange({ ...filters, minRating: value })}
              className={cn(
                "rounded-full border px-2 py-0.5 text-[11px] transition",
                filters.minRating === value
                  ? "border-primary bg-primary text-white"
                  : "border-line text-ink/60 hover:border-primary/40 hover:text-primary",
              )}
            >
              {value === 0 ? "不限" : `${value}+`}
            </button>
          ))}
        </div>
      </div>

      {/* 库存与风险 */}
      <div className="mb-4 space-y-1.5 text-xs text-ink/70">
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={filters.inStockOnly}
            onChange={(event) => onChange({ ...filters, inStockOnly: event.target.checked })}
            className="accent-primary"
          />
          只看有货商品
        </label>
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={filters.excludeRisky}
            onChange={(event) => onChange({ ...filters, excludeRisky: event.target.checked })}
            className="accent-primary"
          />
          排除"谨慎购买"商品
        </label>
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onChange(EMPTY_FILTERS)}
          className="inline-flex items-center gap-1 rounded-lg border border-line px-2.5 py-1.5 text-xs text-ink/60 transition hover:border-primary/40 hover:text-primary"
        >
          <RotateCcw className="h-3 w-3" aria-hidden="true" />
          重置
        </button>
        <button
          type="button"
          onClick={() => {
            const dims: Record<string, string> = {};
            if (filters.budgetMax != null) dims.budget = String(filters.budgetMax);
            if (filters.excludedBrands.length) dims.brands = filters.excludedBrands.join(",");
            if (filters.minRating > 0) dims.rating = String(filters.minRating);
            if (filters.inStockOnly) dims.stock = "1";
            if (filters.excludeRisky) dims.risk = "1";
            onTrack?.("filter_requery", dims);
            onRequery(filtersToQuery(filters, baseQuery));
          }}
          disabled={filters.budgetMax == null && filters.excludedBrands.length === 0 && filters.minRating === 0 && !filters.inStockOnly && !filters.excludeRisky}
          className="flex-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-40"
        >
          按条件重新推荐
        </button>
      </div>
    </aside>
  );
}
