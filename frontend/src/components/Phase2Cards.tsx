/**
 * 二期 S1 前端：偏好中心与会话总结卡
 */
import { useCallback, useEffect, useState } from "react";
import { BookmarkCheck, RefreshCw, Sparkles, Trash2, X } from "lucide-react";
import { API_BASE_URL, authHeaders } from "../lib/agentApiShared";

type Preference = {
  preference_key: string;
  preference_value: string;
  source: string | null;
  updated_at: number | null;
};

type SessionSummary = {
  summary_text: string;
  unresolved_questions: string[];
  focus_products: string[];
};

/** 偏好卡（会话页侧栏/首页入口均可挂） */
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

/** 我的偏好卡（N7.2 会话页 / S1-4） */
export function PreferenceCard({
  preferences,
  onDelete,
}: {
  preferences: Preference[];
  onDelete: (key: string) => void;
}) {
  if (preferences.length === 0) return null;

  return (
    <section className="rounded-xl2 border border-line bg-white p-4 shadow-card">
      <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-ink">
        <BookmarkCheck className="h-4 w-4 text-primary" aria-hidden="true" />
        我的偏好
      </div>
      <div className="space-y-1.5">
        {preferences.map((pref) => (
          <div
            key={pref.preference_key}
            className="flex items-center justify-between gap-2 rounded-lg bg-subtle px-3 py-2"
          >
            <div className="min-w-0">
              <span className="text-xs font-semibold text-ink/75">{pref.preference_key}</span>
              <span className="ml-2 text-xs text-ink/70">{pref.preference_value}</span>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <span
                className={
                  pref.source === "explicit"
                    ? "rounded bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary"
                    : "rounded bg-subtle px-1.5 py-0.5 text-[10px] text-ink/45"
                }
                title={pref.source === "explicit" ? "你手动设置的偏好" : "根据你的咨询记录推断"}
              >
                {pref.source === "explicit" ? "手动" : "推断"}
              </span>
              <button
                type="button"
                onClick={() => onDelete(pref.preference_key)}
                aria-label={`删除偏好 ${pref.preference_key}`}
                className="rounded p-1 text-ink/30 transition hover:bg-risk/10 hover:text-risk"
              >
                <Trash2 className="h-3 w-3" aria-hidden="true" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/** 会话总结卡（S1-5 复访入口） */
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
    <section className="rounded-xl2 border border-primary/25 bg-primary/5 p-4 shadow-card">
      <div className="mb-2 flex items-center justify-between">
        <div className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          上次咨询总结
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭总结"
          className="text-ink/40 transition hover:text-ink"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
      <p className="text-sm leading-6 text-ink/80">{summary.summary_text}</p>

      {summary.unresolved_questions.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-xs font-medium text-ink/50">上次还没确认的问题</div>
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

      {summary.focus_products.length > 0 && (
        <div className="mt-2 text-[11px] text-ink/45">
          上次关注：{summary.focus_products.join("、")}
        </div>
      )}

      <button
        type="button"
        onClick={() => onFollowUp("继续上次的推荐，有没有更便宜的？")}
        className="mt-3 inline-flex items-center gap-1 rounded-full border border-primary/40 bg-white px-3 py-1 text-xs font-medium text-primary transition hover:bg-primary/5"
      >
        <RefreshCw className="h-3 w-3" aria-hidden="true" />
        继续上次的咨询
      </button>
    </section>
  );
}
