/**
 * 首页：决策输入台（N12.4）
 * 直接进入购买决策输入——不做营销落地页。
 * 左 7 栏：主输入 + 条件提示；右 5 栏：最近决策、热门问题、场景入口。
 */
import { ArrowRight, Clock, Sparkles } from "lucide-react";
import { useState } from "react";
import type { ShoppingSessionSummary } from "../types/shopping";

type ShoppingHomeProps = {
  sessions: ShoppingSessionSummary[];
  onSubmit: (query: string) => void;
  onOpenSession: (sessionId: string) => void;
  /** findings N11.16：导购进行中时禁用快捷入口并给出提示 */
  isStreaming?: boolean;
};

// N3.2/N12.4 场景快捷入口（绑定品类和场景的模板问题）
const SCENES: Array<{ label: string; query: string }> = [
  { label: "租房好物", query: "一个人租房，推荐一些实用的家居好物，预算500以内" },
  { label: "送礼", query: "送朋友生日礼物，预算300到500，有点质感的" },
  { label: "母婴", query: "有哪些母婴用品值得入手？" },
  { label: "厨房小电器", query: "想买一个空气炸锅，预算500以内，帮我推荐一下" },
  { label: "数码配件", query: "推荐几款实用的数码配件，预算200以内" },
  { label: "家居收纳", query: "小户型收纳有什么好物推荐？" },
];

// N3.3 热门问题（N12.4 改紧凑列表）
const HOT_QUESTIONS = [
  { question: "想买一个空气炸锅，预算500以内，帮我推荐一下", tag: "厨房小电器 · 预算" },
  { question: "给刚出生的宝宝买东西，该准备点什么", tag: "母婴 · 新手" },
  { question: "摩飞空气炸锅有什么坑？值不值得买", tag: "避坑" },
  { question: "300 以内买个保温杯送长辈，要有质感的", query: "300以内买个保温杯送长辈，要有质感一点的", tag: "送礼 · 预算" },
];

// N12.4 条件提示：预算 / 场景 / 偏好 / 排除项
const CONDITION_HINTS = [
  { label: "预算", example: "500 以内" },
  { label: "场景", example: "租房、送长辈" },
  { label: "偏好", example: "好清洗、低噪音" },
  { label: "排除项", example: "不要摩飞" },
];

// N11.6 标题兜底：过短/纯数字标题不可用（与 App.displayTitle 同规则）
function displayTitle(title: string | null | undefined, fallback: string | null | undefined): string {
  const t = (title ?? "").trim();
  if (t.length >= 4 && !/^\d+$/.test(t)) return t;
  const f = (fallback ?? "").trim();
  if (f.length >= 4 && !/^\d+$/.test(f)) return f.slice(0, 24);
  return "导购咨询";
}

export function ShoppingHome({ sessions, onSubmit, onOpenSession, isStreaming }: ShoppingHomeProps) {
  const [draft, setDraft] = useState("");

  const submit = () => {
    const query = draft.trim();
    if (query && !isStreaming) onSubmit(query);
  };

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10 lg:py-14">
      {/* 12 栏：左 7 主输入 / 右 5 决策资产（N12.4） */}
      <div className="grid gap-10 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <div className="mb-4 inline-flex items-center gap-1.5 rounded-full bg-primary-soft px-3 py-1 text-xs font-semibold text-primary">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            PickMate AI
          </div>
          <h1 className="text-[34px] font-bold leading-[1.15] tracking-tight text-ink xl:text-[40px]">
            买什么，先把条件说清楚
          </h1>
          <p className="mt-3 max-w-xl text-[15px] leading-6 text-ink/60">
            描述你的购买需求，AI 帮你核对价格、评价、风险和适配度，
            给出可解释的推荐与 2~4 款横向对比。
          </p>

          {/* 主输入区（唯一入口；N11.14：首页不出现 textarea，88px 大输入框） */}
          <div className="mt-6 rounded-xl2 border border-line bg-white p-2 shadow-card focus-within:border-primary/60">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && submit()}
              placeholder="描述你的购买需求，例如：想买个空气炸锅预算 500..."
              disabled={Boolean(isStreaming)}
              aria-label="描述购买需求"
              className="h-[88px] min-w-0 flex-1 bg-transparent px-4 text-[15px] outline-none placeholder:text-ink/35 disabled:opacity-60"
            />
            <div className="flex items-center justify-between gap-3 px-2 pb-1">
              <span className="text-[11px] text-ink/40">Enter 提交 · 最多 500 字</span>
              <button
                type="button"
                onClick={submit}
                disabled={!draft.trim() || Boolean(isStreaming)}
                className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-lg bg-primary px-5 text-sm font-semibold text-white transition hover:bg-primary-dark active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
              >
                问导购
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>

          {/* 条件提示（N12.4）：预算 / 场景 / 偏好 / 排除项 */}
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
            {CONDITION_HINTS.map((hint) => (
              <span key={hint.label} className="text-xs text-ink/50">
                <span className="font-semibold text-ink/70">{hint.label}</span>
                <span className="ml-1.5">{hint.example}</span>
              </span>
            ))}
          </div>
        </div>

        <div className="space-y-8 lg:col-span-5">
          {/* 最近决策（N3.4/N12.4）：最多 3 条 */}
          {sessions.length > 0 && (
            <section>
              <h2 className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink/40">
                <Clock className="h-3 w-3" aria-hidden="true" />
                最近决策
              </h2>
              <div className="space-y-1.5">
                {sessions.slice(0, 3).map((session) => (
                  <button
                    key={session.session_id}
                    type="button"
                    onClick={() => onOpenSession(session.session_id)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl2 border border-line bg-white px-4 py-2.5 text-left shadow-line transition hover:border-primary/40 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span className="min-w-0 flex-1 truncate text-sm text-ink/80">
                      {displayTitle(session.title, session.last_query)}
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-ink/35" aria-hidden="true" />
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* 热门问题：紧凑列表（N12.4 不再使用大面积重复卡片） */}
          <section>
            <h2 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-ink/40">
              大家都在问
            </h2>
            <ul className="divide-y divide-line rounded-xl2 border border-line bg-white shadow-line">
              {HOT_QUESTIONS.map((item) => (
                <li key={item.question}>
                  <button
                    type="button"
                    onClick={() => onSubmit(item.query ?? item.question)}
                    disabled={isStreaming}
                    className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition hover:bg-soft disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span className="min-w-0 flex-1 truncate text-sm text-ink">{item.question}</span>
                    <span className="shrink-0 rounded bg-soft px-1.5 py-0.5 text-[11px] text-ink/50">
                      {item.tag}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          {/* 场景快捷入口（N3.2） */}
          <section>
            <h2 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-ink/40">
              场景快捷入口
            </h2>
            <div className="flex flex-wrap gap-2">
              {SCENES.map((scene) => (
                <button
                  key={scene.label}
                  type="button"
                  onClick={() => onSubmit(scene.query)}
                  disabled={isStreaming}
                  className="rounded-full border border-line bg-white px-4 py-1.5 text-sm text-ink/75 shadow-line transition hover:border-primary/45 hover:text-primary active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {scene.label}
                </button>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
