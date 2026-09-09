/**
 * 二期 S1 前端：偏好读取 Hook 与会话总结卡（N12.11 统一分组样式）
 * 偏好展示已并入决策侧栏（DecisionSidebar）；本文件保留 usePreferences 与总结卡
 */
import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Sparkles, X } from "lucide-react";
import { API_BASE_URL, authHeaders } from "../lib/agentApiShared";

type Preference = {
  preference_key: string;
  preference_value: string;
  source: string | null;
  updated_at: number | null;
};

export type { Preference };

type SessionSummary = {
  summary_text: string;
  unresolved_questions: string[];
  /** N11.29：后端读出时已解析为商品名称（缺失退化"已关注商品N"） */
  focus_products: string[];
};

/** 偏好读取（登录后启用；决策侧栏消费） */
export function usePreferences(enabled: boolean) {
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(() => {
    if (!enabled) return;
    setLoading(true);
    fetch(`${API_BASE_URL}/api/shopping/preferences`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => setPreferences(d.items ?? []))
      .catch(() => setPreferences([]))
      .finally(() => setLoading(false));
  }, [enabled]);

  useEffect(() => {
    reload();
  }, [reload]);

  const remove = async (key: string) => {
    await fetch(`${API_BASE_URL}/api/shopping/preferences/${encodeURIComponent(key)}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    reload();
  };

  return { preferences, loading, reload, remove };
}

/** 会话总结卡（S1-5 复访入口 / N12.11 统一卡片分组样式） */
export function SessionSummaryCard({
  summary,
  onFollowUp,
  onClose,
}: {
  summary: SessionSummary;
  onFollowUp: (question: string) => void;
  onClose: () => void;
}) {
  return (
    <section className="rounded-xl2 border border-primary/25 bg-primary-soft/60 p-4 shadow-card">
      <div className="mb-2 flex items-center justify-between">
        <div className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          上次咨询总结
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭总结"
          className="grid h-7 w-7 place-items-center rounded-full text-ink/40 transition hover:bg-white hover:text-ink"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
      <p className="text-sm leading-6 text-ink/80">{summary.summary_text}</p>

      {summary.unresolved_questions.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink/45">
            上次还没确认的问题
          </div>
          <div className="flex flex-wrap gap-1.5">
            {summary.unresolved_questions.map((question) => (
              <button
                key={question}
                type="button"
                onClick={() => onFollowUp(question)}
                className="rounded-full border border-line bg-white px-2.5 py-1 text-[11px] text-ink/70 transition hover:border-primary/45 hover:text-primary"
              >
                {question}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* N11.29：只展示商品名称，不出现后端 ID */}
      {summary.focus_products.length > 0 && (
        <div className="mt-2 text-[11px] text-ink/45">
          上次关注：{summary.focus_products.join("、")}
        </div>
      )}

      <button
        type="button"
        onClick={() => onFollowUp("继续上次的推荐，有没有更便宜的？")}
        className="mt-3 inline-flex items-center gap-1 rounded-full border border-primary/40 bg-white px-3 py-1 text-xs font-medium text-primary transition hover:bg-primary-soft active:scale-[0.98]"
      >
        <RefreshCw className="h-3 w-3" aria-hidden="true" />
        继续上次的咨询
      </button>
    </section>
  );
}
