/**
 * 商品横向对比（N5 重构）
 * 商品为列、维度为行；价格最低/评分最高的单元格自动高亮（N5.2）
 */
import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { downloadCsv } from "../lib/csv";
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

// N5.3 维度分组：筛选芯片 -> 维度集合
const DIM_GROUPS: Array<{ key: string; label: string; dims: string[] }> = [
  { key: "all", label: "全部", dims: [] },
  { key: "price", label: "价格", dims: ["商品", "到手价"] },
  { key: "params", label: "参数", dims: ["商品", "关键属性"] },
  { key: "review", label: "评价", dims: ["商品", "评分", "好评关键词"] },
  { key: "risk", label: "风险", dims: ["商品", "风险提示", "不适合"] },
  { key: "fit", label: "适合人群", dims: ["商品", "适合人群"] },
];

export function ComparisonTable({ headers, rows, warning, conclusion }: ComparisonTableProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [dims, setDims] = useState<string[]>([]);
  // N5.3：当前选中的维度分组（默认全部）
  const [dimGroup, setDimGroup] = useState("all");

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

  // N5.3：分组筛选优先于展开/收起；选"全部"时维持原有展开逻辑
  const groupDims = DIM_GROUPS.find((g) => g.key === dimGroup)?.dims ?? [];
  const baseDims = dimGroup === "all" ? dims : dims.filter((d) => groupDims.includes(d));
  const shownDims = expanded || dimGroup !== "all" ? baseDims : baseDims.slice(0, collapsed ? 5 : baseDims.length);
  const productName = (row: Record<string, string>, index: number) =>
    row["商品"] || `商品${index + 1}`;

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
          <button
            type="button"
            onClick={() =>
              downloadCsv(
                "pickmate-对比",
                ["维度", ...rows.map(productName)],
                dims.map((dim) => [dim, ...rows.map((row) => row[dim] || "暂无数据")]),
              )
            }
            className="inline-flex items-center gap-1 rounded border border-line px-2 py-0.5 transition hover:border-primary/40 hover:text-primary"
          >
            <Download className="h-3 w-3" aria-hidden="true" />
            导出 CSV
          </button>
        </div>
      </div>

      {conclusion && (
        <div className="border-b border-line bg-primary/5 px-4 py-2.5 text-xs leading-5 text-primary">
          {conclusion}
        </div>
      )}

      {/* N5.3 维度分组筛选 */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-line px-4 py-2">
        {DIM_GROUPS.filter((g) => g.key === "all" || dims.some((d) => g.dims.includes(d))).map(
          (group) => (
            <button
              key={group.key}
              type="button"
              onClick={() => setDimGroup(group.key)}
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
        <div className="border-b border-line bg-brass/10 px-4 py-2 text-xs text-ink/70">{warning}</div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 w-20 bg-subtle px-3 py-2.5 text-xs font-semibold text-ink/60">
                维度
              </th>
              {rows.map((row, index) => (
                <th
                  key={row.product_id}
                  className="min-w-[180px] bg-subtle px-3 py-2.5 text-xs font-semibold text-ink"
                >
                  <span className="line-clamp-2">{productName(row, index)}</span>
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

      {dimGroup === "all" && dims.length > 5 && (
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
