/**
 * 商品横向对比（N5 重构 / N12.9 / N12.18 / N12.25）
 * 商品为列、维度为行；表头固定商品图/名称/到手价；
 * 价格最低、评分最高、风险最高以颜色 + 文案高亮
 */
import { useEffect, useState } from "react";
import { AlertTriangle, Download } from "lucide-react";
import { downloadCsv } from "../lib/csv";
import { cn } from "../lib/format";

export type CompareProductMeta = {
  product_id: string;
  title: string;
  image_url?: string;
  price: number;
  promotion_price: number | null;
  risk_level?: string;
};

type ComparisonTableProps = {
  headers: string[];
  rows: Array<Record<string, string>>;
  /** N12.18/N12.25：商品元数据（表头图/价与风险高亮），服务端新数据才有 */
  products?: CompareProductMeta[];
  warning?: string;
  conclusion?: string;
  /** N10.3：维度组切换回调（埋点用），未传不影响功能 */
  onDimGroupChange?: (group: string) => void;
};

// 维度展示顺序与简称（未列出的维度排在其后）
const DIM_ORDER = ["商品", "到手价", "评分", "关键属性", "好评关键词", "风险提示", "适合人群", "不适合"];
const DIM_SHORT: Record<string, string> = {
  关键属性: "核心参数",
  风险提示: "差评风险",
  不适合: "不适合",
};

// N5.3 维度分组：筛选芯片 -> 维度集合
const DIM_GROUPS: Array<{ key: string; label: string; dims: string[] }> = [
  { key: "all", label: "全部", dims: [] },
  { key: "price", label: "价格", dims: ["商品", "到手价"] },
  { key: "params", label: "参数", dims: ["商品", "关键属性"] },
  { key: "review", label: "评价", dims: ["商品", "评分", "好评关键词"] },
  { key: "risk", label: "风险", dims: ["商品", "风险提示", "不适合"] },
  { key: "fit", label: "适合人群", dims: ["商品", "适合人群"] },
];

// N12.25：风险等级权重（unknown/低风险不参与"风险最高"高亮）
const RISK_WEIGHT: Record<string, number> = { high: 3, medium: 2, low: 1, unknown: 0 };

export function ComparisonTable({
  headers,
  rows,
  products,
  warning,
  conclusion,
  onDimGroupChange,
}: ComparisonTableProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [dims, setDims] = useState<string[]>([]);
  const [dimGroup, setDimGroup] = useState("all");

  // N12.30：存量对比表（上线前落库，无 products 元数据）从行数据合成表头元数据，
  // 保证新旧记录 UI 一致（缩略图回退品类字块，价格取自到手价行）
  const effectiveProducts: CompareProductMeta[] =
    products && products.length
      ? products
      : rows.map((row, index) => ({
          product_id: row.product_id ?? String(index),
          title: row["商品"] || `商品${index + 1}`,
          price: parseFloat((row["到手价"] ?? "").replace(/[^\d.]/g, "")) || 0,
          promotion_price: null,
        }));
  const hasMeta = effectiveProducts.length > 0;

  useEffect(() => {
    const ordered = [
      ...DIM_ORDER.filter((dim) => headers.includes(dim)),
      ...headers.filter((header) => !DIM_ORDER.includes(header) && header !== "product_id"),
    ];
    setDims(ordered);
  }, [headers]);

  if (rows.length === 0) return null;

  // 高亮计算（N5.2）：到手价最低、评分最高
  const priceOf = (row: Record<string, string>) =>
    parseFloat((row["到手价"] ?? "").replace(/[^\d.]/g, "")) || Infinity;
  const ratingOf = (row: Record<string, string>) =>
    parseFloat((row["评分"] ?? "").replace(/^([\d.]+).*/, "$1")) || 0;
  const cheapestId = rows.reduce((best, row) => (priceOf(row) < priceOf(best) ? row : best), rows[0])
    ?.product_id;
  const bestRatingId = rows.reduce(
    (best, row) => (ratingOf(row) > ratingOf(best) ? row : best),
    rows[0],
  )?.product_id;

  // N12.25：风险最高（medium 及以上才按等级高亮；并列全部标出）
  const productsById = new Map(effectiveProducts.map((p) => [p.product_id, p]));
  const maxRisk = Math.max(
    ...effectiveProducts.map((p) => RISK_WEIGHT[p.risk_level ?? "unknown"] ?? 0),
    0,
  );
  let highestRiskIds = new Set(
    maxRisk >= 2
      ? effectiveProducts
          .filter((p) => (RISK_WEIGHT[p.risk_level ?? "unknown"] ?? 0) === maxRisk)
          .map((p) => p.product_id)
      : [],
  );
  // N12.29：等级不足以区分（全部 low/unknown）时，从风险行文本的差评百分比
  // 兜底解析最高者（如 4% vs 12% 高亮 12%）；无百分比或并列低值不高亮
  if (highestRiskIds.size === 0) {
    const percentOf = (row: Record<string, string>) => {
      const match = (row["风险提示"] ?? "").match(/(\d+(?:\.\d+)?)\s*%/);
      return match ? parseFloat(match[1]) : -1;
    };
    const percents = rows.map((row) => ({ id: row.product_id ?? "", pct: percentOf(row) }));
    const maxPercent = Math.max(...percents.map((p) => p.pct));
    if (maxPercent > 0) {
      highestRiskIds = new Set(
        percents.filter((p) => p.pct === maxPercent).map((p) => p.id),
      );
    }
  }

  // N12.18：表头已固定到手价，数据行不再重复展示（CSV 导出仍保留完整维度）
  const visibleDims = hasMeta ? dims.filter((d) => d !== "到手价") : dims;

  const groupDims = DIM_GROUPS.find((g) => g.key === dimGroup)?.dims ?? [];
  const baseDims = dimGroup === "all" ? visibleDims : visibleDims.filter((d) => groupDims.includes(d));
  const shownDims = expanded || dimGroup !== "all" ? baseDims : baseDims.slice(0, collapsed ? 5 : baseDims.length);
  const productName = (row: Record<string, string>, index: number) =>
    row["商品"] || `商品${index + 1}`;

  const cellClass = (dim: string, row: Record<string, string>) =>
    cn(
      "px-3 py-2.5 align-top text-xs leading-5",
      (dim === "风险提示" || dim === "不适合") && "text-risk/85",
      dim === "到手价" && row.product_id === cheapestId && "bg-price/10 font-semibold text-price",
      dim === "评分" && row.product_id === bestRatingId && "bg-good/10 font-semibold text-good",
      // N12.25：风险最高的商品整列风险提示加底色（配合表头"风险最高"文案）
      dim === "风险提示" && highestRiskIds.has(row.product_id ?? "") && "bg-risk/10 font-semibold",
    );

  return (
    <section className="mt-3 overflow-hidden rounded-xl2 border border-line bg-white shadow-card">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="text-sm font-semibold text-ink">商品横向对比</div>
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
          <span className="rounded bg-price/10 px-1.5 py-0.5 text-price">价格最低</span>
          <span className="rounded bg-good/10 px-1.5 py-0.5 text-good">评分最高</span>
          {highestRiskIds.size > 0 && (
            <span className="rounded bg-risk/10 px-1.5 py-0.5 text-risk">风险最高</span>
          )}
          <button
            type="button"
            onClick={() =>
              downloadCsv(
                "pickmate-对比",
                ["维度", ...rows.map(productName)],
                dims.map((dim) => [dim, ...rows.map((row) => row[dim] || "暂无数据")]),
              )
            }
            className="inline-flex items-center gap-1 rounded border border-line px-2 py-0.5 transition hover:border-primary/40 hover:text-primary active:scale-[0.98]"
          >
            <Download className="h-3 w-3" aria-hidden="true" />
            导出 CSV
          </button>
        </div>
      </div>

      {conclusion && (
        <div className="border-b border-line bg-primary-soft px-4 py-2.5 text-xs leading-5 text-primary">
          {conclusion}
        </div>
      )}

      {/* N5.3 维度分组筛选 */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-line px-4 py-2">
        {DIM_GROUPS.filter((g) => g.key === "all" || visibleDims.some((d) => g.dims.includes(d))).map(
          (group) => (
            <button
              key={group.key}
              type="button"
              onClick={() => {
                setDimGroup(group.key);
                onDimGroupChange?.(group.key);
              }}
              className={cn(
                "rounded-full px-2.5 py-0.5 text-[11px] font-medium transition",
                dimGroup === group.key
                  ? "bg-primary text-white"
                  : "bg-subtle text-ink/55 hover:text-ink",
              )}
            >
              {group.label}
            </button>
          ),
        )}
      </div>
      {warning && (
        <div className="border-b border-line bg-warning/10 px-4 py-2 text-xs text-ink/70">{warning}</div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 w-20 bg-subtle px-3 py-2.5 text-xs font-semibold text-ink/60">
                维度
              </th>
              {rows.map((row, index) => {
                const meta = productsById.get(row.product_id ?? "");
                return (
                  <th
                    key={row.product_id}
                    className="min-w-[180px] bg-subtle px-3 py-2.5 text-xs font-semibold text-ink align-top"
                  >
                    {/* N12.18：表头固定商品图 / 名称 / 到手价 / 风险结论 */}
                    {meta ? (
                      <div className="flex items-start gap-2.5 text-left">
                        <ProductThumb meta={meta} />
                        <div className="min-w-0">
                          <span className="line-clamp-2 leading-4">{meta.title}</span>
                          <span className="mt-1 block text-[13px] font-bold tabular-nums text-price">
                            ¥{meta.promotion_price ?? meta.price}
                          </span>
                          {highestRiskIds.has(meta.product_id) && (
                            <span className="mt-1 inline-flex items-center gap-0.5 rounded bg-risk/10 px-1 py-0.5 text-[10px] font-medium text-risk">
                              <AlertTriangle className="h-2.5 w-2.5" aria-hidden="true" />
                              风险最高
                            </span>
                          )}
                        </div>
                      </div>
                    ) : (
                      <span className="line-clamp-2">{productName(row, index)}</span>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {shownDims
              .filter((dim) => dim !== "商品")
              .map((dim) => (
                <tr key={dim} className="border-t border-line">
                  <td className="sticky left-0 z-10 bg-white px-3 py-2.5 text-xs font-medium text-muted">
                    {DIM_SHORT[dim] ?? dim}
                  </td>
                  {rows.map((row) => (
                    <td key={row.product_id} className={cellClass(dim, row)}>
                      {row[dim] || "暂无数据"}
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {dimGroup === "all" && visibleDims.length > 5 && (
        <button
          type="button"
          onClick={() => {
            setExpanded((value) => !value);
            setCollapsed(false);
          }}
          className="w-full border-t border-line py-2 text-xs font-medium text-primary transition hover:bg-primary-soft"
        >
          {expanded ? "收起维度" : `展开全部 ${visibleDims.length} 个维度`}
        </button>
      )}
    </section>
  );
}

/** N12.18：表头商品缩略图（112 图体系的缩小版；失败回退品类字块） */
function ProductThumb({ meta }: { meta: CompareProductMeta }) {
  const [failed, setFailed] = useState(false);
  if (!meta.image_url || failed) {
    return (
      <span
        aria-hidden="true"
        className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-soft text-[11px] font-semibold text-primary"
      >
        {meta.title.slice(0, 2)}
      </span>
    );
  }
  return (
    <img
      src={meta.image_url}
      alt={meta.title}
      loading="lazy"
      onError={() => setFailed(true)}
      className="h-12 w-12 shrink-0 rounded-lg object-cover"
    />
  );
}
