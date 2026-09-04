/**
 * 商品横向对比（N5 重构）
 * 商品为列、维度为行；价格最低/评分最高的单元格自动高亮（N5.2）
 */
import { useEffect, useState } from "react";
import { cn } from "../lib/format";

type ComparisonTableProps = {
  headers: string[];
  rows: Array<Record<string, string>>;
  warning?: string;
  conclusion?: string;
};

// 维度展示顺序与简称（未列出的维度排在其后）
const DIM_ORDER = ["商品", "到手价", "评分", "关键属性", "好评关键词", "风险提示", "适合人群", "不适合"];
const DIM_SHORT: Record<string, string> = {
  关键属性: "核心参数",
  风险提示: "差评风险",
  不适合: "不适合",
};

export function ComparisonTable({ headers, rows, warning, conclusion }: ComparisonTableProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [dims, setDims] = useState<string[]>([]);

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

  const shownDims = expanded ? dims : dims.slice(0, collapsed ? 5 : dims.length);

  const cellClass = (dim: string, row: Record<string, string>) =>
    cn(
      "px-3 py-2.5 align-top text-xs leading-5",
      dim === "商品" && "font-semibold text-ink",
      (dim === "风险提示" || dim === "不适合") && "text-risk/85",
      dim === "到手价" && row.product_id === cheapestId && "bg-price/10 font-semibold text-price",
      dim === "评分" && row.product_id === bestRatingId && "bg-good/10 font-semibold text-good",
    );

  return (
    <section className="mt-3 overflow-hidden rounded-xl2 border border-line bg-white shadow-card">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="text-sm font-semibold text-ink">商品横向对比</div>
        <div className="flex items-center gap-2 text-[11px] text-ink/45">
          <span className="rounded bg-price/10 px-1.5 py-0.5 text-price">价格最低</span>
          <span className="rounded bg-good/10 px-1.5 py-0.5 text-good">评分最高</span>
        </div>
      </div>

      {conclusion && (
        <div className="border-b border-line bg-primary/5 px-4 py-2.5 text-xs leading-5 text-primary">
          {conclusion}
        </div>
      )}
      {warning && (
        <div className="border-b border-line bg-brass/10 px-4 py-2 text-xs text-ink/70">{warning}</div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 w-20 bg-subtle px-3 py-2.5 text-xs font-semibold text-ink/60">
                维度
              </th>
              {rows.map((row) => (
                <th
                  key={row.product_id}
                  className="min-w-[180px] bg-subtle px-3 py-2.5 text-xs font-semibold text-ink"
                >
                  <span className="line-clamp-2">{row["商品"]}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shownDims
              .filter((dim) => dim !== "商品")
              .map((dim) => (
                <tr key={dim} className="border-t border-line">
                  <td className="sticky left-0 z-10 bg-white px-3 py-2.5 text-xs font-medium text-ink/55">
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

      {dims.length > 5 && (
        <button
          type="button"
          onClick={() => {
            setExpanded((value) => !value);
            setCollapsed(false);
          }}
          className="w-full border-t border-line py-2 text-xs font-medium text-primary transition hover:bg-primary/5"
        >
          {expanded ? "收起维度" : `展开全部 ${dims.length} 个维度`}
        </button>
      )}
    </section>
  );
}
