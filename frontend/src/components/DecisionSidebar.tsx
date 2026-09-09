/**
 * 决策侧栏（N12.5 对话页三段式工作区）
 * 固定在对话页右侧（xl 及以上显示；小屏由 App 折叠为 composer 上方条）：
 * 当前条件 / 我的偏好 / 对比托盘 / 当前会话操作
 */
import { ListRestart, Plus, RefreshCw, Square, Trash2, X } from "lucide-react";
import { cn } from "../lib/format";

export type SidebarPreference = {
  preference_key: string;
  preference_value: string;
  source: string | null;
};

type DecisionSidebarProps = {
  conditions: string[];
  preferences: SidebarPreference[];
  onDeletePreference: (key: string) => void;
  compareIds: string[];
  productTitleById: Map<string, string>;
  onRemoveCompare: (productId: string) => void;
  onSubmitCompare: () => void;
  isStreaming: boolean;
  onStop: () => void;
  onRegenerate: () => void;
  onNewConsult: () => void;
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl2 border border-line bg-white p-4 shadow-card">
      <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink/40">
        {title}
      </h3>
      {children}
    </section>
  );
}

const EMPTY_HINT = "暂无数据";

export function DecisionSidebar({
  conditions,
  preferences,
  onDeletePreference,
  compareIds,
  productTitleById,
  onRemoveCompare,
  onSubmitCompare,
  isStreaming,
  onStop,
  onRegenerate,
  onNewConsult,
}: DecisionSidebarProps) {
  const compareReady = compareIds.length >= 2 && !isStreaming;

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* 1. 当前条件 */}
      <Section title="当前条件">
        {conditions.length === 0 ? (
          <p className="text-xs leading-5 text-ink/40">{EMPTY_HINT}。发起咨询后，这里会汇总品类、预算、场景与排除项。</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {conditions.map((condition) => (
              <span
                key={condition}
                className="inline-flex items-center rounded-full bg-primary-soft px-2.5 py-0.5 text-[11px] font-medium text-primary"
              >
                {condition}
              </span>
            ))}
          </div>
        )}
      </Section>

      {/* 2. 我的偏好 */}
      <Section title="我的偏好">
        {preferences.length === 0 ? (
          <p className="text-xs leading-5 text-ink/40">
            {EMPTY_HINT}。登录后系统会根据咨询记录推断偏好，也可手动维护。
          </p>
        ) : (
          <ul className="space-y-1.5">
            {preferences.slice(0, 6).map((pref) => (
              <li
                key={pref.preference_key}
                className="flex items-center justify-between gap-2 rounded-lg bg-soft px-2.5 py-1.5"
              >
                <span className="min-w-0 truncate text-xs">
                  <span className="font-semibold text-ink/75">{pref.preference_key}</span>
                  <span className="ml-1.5 text-ink/60">{pref.preference_value}</span>
                </span>
                <span className="flex shrink-0 items-center gap-1.5">
                  <span
                    className={cn(
                      "rounded px-1 py-0.5 text-[10px]",
                      pref.source === "explicit"
                        ? "bg-primary-soft text-primary"
                        : "bg-subtle text-ink/45",
                    )}
                    title={pref.source === "explicit" ? "你手动设置的偏好" : "根据你的咨询记录推断"}
                  >
                    {pref.source === "explicit" ? "手动" : "推断"}
                  </span>
                  <button
                    type="button"
                    onClick={() => onDeletePreference(pref.preference_key)}
                    aria-label={`删除偏好 ${pref.preference_key}`}
                    className="rounded p-1 text-ink/30 transition hover:bg-risk/10 hover:text-risk"
                  >
                    <Trash2 className="h-3 w-3" aria-hidden="true" />
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* 3. 对比托盘（N12.8） */}
      <Section title={`对比托盘 ${compareIds.length}/4`}>
        {compareIds.length === 0 ? (
          <p className="text-xs leading-5 text-ink/40">
            在推荐卡或详情抽屉点「加入对比」，选 2~4 款后开始横向对比。
          </p>
        ) : (
          <>
            <ul className="space-y-1.5">
              {compareIds.map((id, index) => {
                const title = productTitleById.get(id) ?? `商品${index + 1}`;
                return (
                  <li
                    key={id}
                    className="flex items-center justify-between gap-2 rounded-lg bg-soft px-2.5 py-1.5"
                  >
                    <span className="min-w-0 flex-1 truncate text-xs text-ink/80" title={title}>
                      {title}
                    </span>
                    <button
                      type="button"
                      onClick={() => onRemoveCompare(id)}
                      aria-label={`移除 ${title}`}
                      className="shrink-0 rounded p-1 text-ink/35 transition hover:bg-risk/10 hover:text-risk"
                    >
                      <X className="h-3 w-3" aria-hidden="true" />
                    </button>
                  </li>
                );
              })}
            </ul>
            <button
              type="button"
              onClick={onSubmitCompare}
              disabled={!compareReady}
              title={compareReady ? undefined : "至少选 2 款商品才能开始对比"}
              className="mt-2.5 inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-primary text-sm font-semibold text-white transition hover:bg-primary-dark active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5 rotate-45" aria-hidden="true" />
              开始对比（{compareIds.length}/4）
            </button>
            {!compareReady && compareIds.length === 1 && (
              <p className="mt-1.5 text-[11px] leading-4 text-ink/45">再选 1 款即可开始对比。</p>
            )}
          </>
        )}
      </Section>

      {/* 4. 当前会话操作 */}
      <Section title="当前会话">
        <div className="grid gap-1.5">
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-risk/40 px-3 text-sm font-medium text-risk transition hover:bg-risk/5 active:scale-[0.98]"
            >
              <Square className="h-3 w-3 fill-current" aria-hidden="true" />
              停止本次导购
            </button>
          ) : (
            <button
              type="button"
              onClick={onRegenerate}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-line px-3 text-sm text-ink/70 transition hover:border-primary/40 hover:text-primary active:scale-[0.98]"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              重新生成上一问
            </button>
          )}
          <button
            type="button"
            onClick={onNewConsult}
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-line px-3 text-sm text-ink/70 transition hover:border-primary/40 hover:text-primary active:scale-[0.98]"
          >
            <ListRestart className="h-3.5 w-3.5" aria-hidden="true" />
            新咨询
          </button>
        </div>
      </Section>
    </div>
  );
}
