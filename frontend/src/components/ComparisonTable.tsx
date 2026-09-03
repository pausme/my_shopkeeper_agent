/**
 * 商品横向对比表
 * 渲染后端 comparison 事件的 headers/rows 结构
 */

type ComparisonTableProps = {
  headers: string[];
  rows: Array<Record<string, string>>;
  warning?: string;
};

export function ComparisonTable({ headers, rows, warning }: ComparisonTableProps) {
  if (rows.length === 0) return null;

  return (
    <section className="mt-3 overflow-hidden border border-ink/10 bg-white/70 shadow-line">
      <div className="border-b border-ink/10 px-4 py-2.5 text-sm font-semibold text-ink">
        商品横向对比
      </div>
      {warning && (
        <div className="border-b border-brass/30 bg-brass/10 px-4 py-2 text-xs text-ink/70">
          {warning}
        </div>
      )}
      <div className="max-h-[340px] overflow-auto">
        <table className="min-w-full border-separate border-spacing-0 text-left text-xs">
          <thead className="sticky top-0 z-10 bg-[#efe6d8]">
            <tr>
              {headers.map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="whitespace-nowrap border-b border-ink/10 px-3 py-2.5 font-semibold text-ink/70"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="odd:bg-white/45 even:bg-white/20">
                {headers.map((header) => (
                  <td
                    key={header}
                    className="max-w-[220px] border-b border-ink/5 px-3 py-2.5 align-top text-ink/80"
                  >
                    {row[header] || "-"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
