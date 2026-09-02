/**
 * 查询结果展示组件
 * 提供表格 / 柱状图两种视图：分组统计类结果更适合图表阅读
 */
import { BarChart3, Table2 } from "lucide-react";
import { useState } from "react";
import { cn } from "../lib/format";
import { ResultTable } from "./ResultTable";

type Row = Record<string, unknown>;

const SERIES_COLORS = ["#3f7a52", "#b08d57", "#5b7c99", "#8a5f7d"];

function normalizeRows(data: unknown): Row[] {
  if (Array.isArray(data)) {
    return data.map((item) =>
      item && typeof item === "object" && !Array.isArray(item)
        ? (item as Row)
        : {},
    );
  }
  if (data && typeof data === "object") {
    return [data as Row];
  }
  return [];
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function analyze(rows: Row[]) {
  const columns = Array.from(
    rows.reduce((keys, row) => {
      Object.keys(row).forEach((key) => keys.add(key));
      return keys;
    }, new Set<string>()),
  );
  const numericColumns = columns.filter((column) =>
    rows.some((row) => toNumber(row[column]) !== null),
  );
  const labelColumn = columns.find((column) => !numericColumns.includes(column));
  return { columns, numericColumns, labelColumn };
}

function ResultChart({ rows, numericColumns, labelColumn }: {
  rows: Row[];
  numericColumns: string[];
  labelColumn: string;
}) {
  // 按第一个数值列降序，最多展示 12 条避免图过高
  const sorted = [...rows]
    .map((row) => ({
      label: String(row[labelColumn] ?? "-"),
      values: numericColumns.map((column) => toNumber(row[column]) ?? 0),
    }))
    .sort((a, b) => b.values[0] - a.values[0])
    .slice(0, 12);

  const maxValue = Math.max(
    ...sorted.map((item) => Math.max(...item.values.map((v) => Math.abs(v)))),
    1,
  );
  const rowHeight = 26 + numericColumns.length * 8;
  const chartHeight = sorted.length * rowHeight + 28;
  const labelWidth = 150;
  const barMaxWidth = 560;

  return (
    <div className="max-h-[360px] overflow-auto p-4">
      <svg
        viewBox={`0 0 740 ${chartHeight}`}
        className="w-full min-w-[560px]"
        role="img"
        aria-label="查询结果柱状图"
      >
        {sorted.map((item, index) => {
          const baseY = 14 + index * rowHeight;
          return (
            <g key={`${item.label}-${index}`}>
              <text
                x={labelWidth - 8}
                y={baseY + rowHeight / 2 + 4}
                textAnchor="end"
                fontSize="13"
                fill="rgba(32,32,29,0.75)"
              >
                {item.label.length > 10 ? `${item.label.slice(0, 10)}…` : item.label}
              </text>
              {item.values.map((value, seriesIndex) => {
                const width = Math.max(
                  (Math.abs(value) / maxValue) * barMaxWidth,
                  value === 0 ? 0 : 2,
                );
                const barY = baseY + seriesIndex * 9;
                return (
                  <g key={seriesIndex}>
                    <rect
                      x={labelWidth}
                      y={barY}
                      width={width}
                      height={8}
                      fill={SERIES_COLORS[seriesIndex % SERIES_COLORS.length]}
                      opacity={0.88}
                    />
                    <text
                      x={labelWidth + width + 6}
                      y={barY + 8}
                      fontSize="11"
                      fill="rgba(32,32,29,0.65)"
                      fontFamily="ui-monospace, monospace"
                    >
                      {value.toLocaleString("zh-CN")}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}
        {numericColumns.length > 1 && (
          <g>
            {numericColumns.map((column, index) => (
              <g key={column}>
                <rect
                  x={labelWidth + index * 130}
                  y={chartHeight - 12}
                  width={10}
                  height={10}
                  fill={SERIES_COLORS[index % SERIES_COLORS.length]}
                />
                <text x={labelWidth + index * 130 + 14} y={chartHeight - 3} fontSize="11" fill="rgba(32,32,29,0.65)">
                  {column}
                </text>
              </g>
            ))}
          </g>
        )}
      </svg>
    </div>
  );
}

export function ResultView({ data }: { data: unknown }) {
  const rows = normalizeRows(data);
  const { numericColumns, labelColumn } = analyze(rows);
  const chartable = rows.length > 0 && numericColumns.length > 0 && Boolean(labelColumn);
  const [view, setView] = useState<"table" | "chart">("table");

  if (rows.length === 0) return null;

  return (
    <section className="mt-4 overflow-hidden border border-ink/10 bg-white/70 shadow-line">
      <div className="flex items-center justify-between border-b border-ink/10 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          <BarChart3 className="h-4 w-4 text-moss" aria-hidden="true" />
          查询结果
        </div>
        {chartable && (
          <div className="flex items-center border border-ink/15 bg-white/60 text-xs">
            <button
              type="button"
              onClick={() => setView("table")}
              className={cn(
                "flex items-center gap-1 px-3 py-1.5 transition",
                view === "table" ? "bg-ink text-parchment" : "text-ink/60 hover:text-ink",
              )}
            >
              <Table2 className="h-3.5 w-3.5" aria-hidden="true" />
              表格
            </button>
            <button
              type="button"
              onClick={() => setView("chart")}
              className={cn(
                "flex items-center gap-1 px-3 py-1.5 transition",
                view === "chart" ? "bg-ink text-parchment" : "text-ink/60 hover:text-ink",
              )}
            >
              <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" />
              图表
            </button>
          </div>
        )}
      </div>
      {view === "chart" && chartable && labelColumn ? (
        <ResultChart rows={rows} numericColumns={numericColumns} labelColumn={labelColumn} />
      ) : (
        <ResultTable data={data} />
      )}
    </section>
  );
}
