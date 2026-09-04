/**
 * 导购首页（N3）
 * 搜索前置、场景快捷入口、热门问题卡、最近会话、新手引导
 */
import { ArrowRight, Clock, Sparkles } from "lucide-react";
import { useState } from "react";
import type { ShoppingSessionSummary } from "../types/shopping";

type ShoppingHomeProps = {
  sessions: ShoppingSessionSummary[];
  onSubmit: (query: string) => void;
  onOpenSession: (sessionId: string) => void;
};

// N3.2 场景快捷入口（绑定品类和场景的模板问题）
const SCENES: Array<{ label: string; query: string }> = [
  { label: "租房好物", query: "一个人租房，推荐一些实用的家居好物，预算500以内" },
  { label: "送礼", query: "送朋友生日礼物，预算300到500，有点质感的" },
  { label: "母婴", query: "有哪些母婴用品值得入手？" },
  { label: "厨房小电器", query: "想买一个空气炸锅，预算500以内，帮我推荐一下" },
  { label: "数码配件", query: "推荐几款实用的数码配件，预算200以内" },
  { label: "家居收纳", query: "小户型收纳有什么好物推荐？" },
];

// N3.3 热门问题卡
const HOT_QUESTIONS = [
  { question: "想买一个空气炸锅，预算500以内，帮我推荐一下", tag: "厨房小电器 · 预算" },
  { question: "给刚出生的宝宝买东西，该准备点什么", tag: "母婴 · 新手" },
  { question: "摩飞空气炸锅有什么坑？值不值得买", tag: "避坑" },
  { question: "300 以内买个保温杯送长辈，要有质感的", query: "300以内买个保温杯送长辈，要有质感一点的", tag: "送礼 · 预算" },
];

export function ShoppingHome({ sessions, onSubmit, onOpenSession }: ShoppingHomeProps) {
  const [draft, setDraft] = useState("");

  const submit = () => {
    const query = draft.trim();
    if (query) onSubmit(query);
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-10 lg:py-14">
      {/* 主标题 + 搜索前置（N3.1） */}
      <div className="text-center">
        <div className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
          PickMate AI
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">
          买什么，问导购
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-ink/55">
          描述你的购买需求，AI 帮你召回候选、分析评价与风险，给出可解释的推荐与横向对比。
        </p>
      </div>

      {/* 搜索框（页面核心） */}
      <div className="mx-auto mt-7 flex max-w-xl items-center gap-2 rounded-xl2 border border-line bg-white p-2 shadow-card focus-within:border-primary/60">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && submit()}
          placeholder="描述你的购买需求，例如：想买个空气炸锅预算 500..."
          className="min-w-0 flex-1 bg-transparent px-3 text-sm outline-none placeholder:text-ink/35"
          autoFocus
        />
        <button
          type="button"
          onClick={submit}
          disabled={!draft.trim()}
          className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-40"
        >
          问导购
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
      {/* 新手引导（N3.5） */}
      <p className="mt-2.5 text-center text-[11px] text-ink/40">
        试试说清楚：预算 + 使用场景 + 偏好 + 排除项，推荐会更精准
      </p>

      {/* 场景快捷入口（N3.2） */}
      <div className="mt-8">
        <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink/40">
          场景快捷入口
        </div>
        <div className="flex flex-wrap gap-2">
          {SCENES.map((scene) => (
            <button
              key={scene.label}
              type="button"
              onClick={() => onSubmit(scene.query)}
              className="rounded-full border border-line bg-white px-4 py-1.5 text-sm text-ink/75 shadow-line transition hover:border-primary/45 hover:text-primary"
            >
              {scene.label}
            </button>
          ))}
        </div>
      </div>

      {/* 热门问题卡（N3.3） */}
      <div className="mt-8">
        <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink/40">
          大家都在问
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {HOT_QUESTIONS.map((item) => (
            <button
              key={item.question}
              type="button"
              onClick={() => onSubmit(item.query ?? item.question)}
              className="rounded-xl2 border border-line bg-white p-4 text-left shadow-card transition hover:border-primary/40"
            >
              <div className="text-sm leading-5 text-ink">{item.question}</div>
              <div className="mt-1.5 text-[11px] text-primary/80">{item.tag}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 最近会话（N3.4） */}
      {sessions.length > 0 && (
        <div className="mt-8">
          <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink/40">
            <Clock className="h-3 w-3" aria-hidden="true" />
            最近咨询
          </div>
          <div className="space-y-2">
            {sessions.slice(0, 3).map((session) => (
              <button
                key={session.session_id}
                type="button"
                onClick={() => onOpenSession(session.session_id)}
                className="flex w-full items-center justify-between gap-3 rounded-xl2 border border-line bg-white px-4 py-3 text-left shadow-line transition hover:border-primary/40"
              >
                <span className="min-w-0 flex-1 truncate text-sm text-ink/80">
                  {session.title || session.last_query || "未命名咨询"}
                </span>
                <ArrowRight className="h-3.5 w-3.5 shrink-0 text-ink/35" aria-hidden="true" />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
