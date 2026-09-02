/**
 * 前端应用主组件
 * 负责多会话管理、聊天状态、SSE 事件消费和整体页面布局
 * 会话持久化在 localStorage，切换/新建/删除均在本地完成
 */
import {
  Activity,
  BarChart3,
  Eraser,
  History,
  KeyRound,
  Leaf,
  MessageSquarePlus,
  Server,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Composer } from "./components/Composer";
import { EmptyState } from "./components/EmptyState";
import { MessageBubble } from "./components/MessageBubble";
import { ApiError, streamQuery } from "./lib/agentApi";
import { cn, summarizeResult } from "./lib/format";
import { getApiToken, loadConversations, saveConversations, setApiToken } from "./lib/storage";
import type { AgentEvent, ChatMessage, Conversation, StepState } from "./types/agent";

const examples = [
  "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
  "统计 2025 年 3 月各商品品类的销量和销售额",
  "查询华东地区 2025 年第一季度销售额最高的前 5 个商品",
  "按会员等级统计 2025 年第一季度的订单数和销售额",
];

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

function makeId() {
  return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createConversation(): Conversation {
  return {
    id: makeId(),
    title: "新会话",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  };
}

function upsertStep(steps: StepState[] = [], event: Extract<AgentEvent, { type: "progress" }>) {
  const existing = steps.find((item) => item.step === event.step);
  const next = steps.filter((item) => item.step !== event.step);
  next.push({
    step: event.step,
    status: event.status,
    updatedAt: Date.now(),
    // 保留首次进入 running 的时间，用于计算步骤耗时
    startedAt: existing?.startedAt ?? Date.now(),
  });
  return next;
}

function applyEvent(message: ChatMessage, event: AgentEvent): ChatMessage {
  if (event.type === "progress") {
    return {
      ...message,
      content: event.status === "running" ? `正在执行：${event.step}` : message.content,
      steps: upsertStep(message.steps, event),
    };
  }

  if (event.type === "result") {
    return {
      ...message,
      status: "done",
      content: summarizeResult(event.data),
      result: event.data,
    };
  }

  return {
    ...message,
    status: "error",
    content: "这次查询没有成功。",
    error: event.message,
  };
}

export default function App() {
  const initialConversations = useMemo(() => {
    const loaded = loadConversations();
    return loaded.length > 0 ? loaded : [createConversation()];
  }, []);

  const [conversations, setConversations] = useState<Conversation[]>(initialConversations);
  const [activeId, setActiveId] = useState<string>(initialConversations[0].id);
  const [draft, setDraft] = useState("");
  const [activeController, setActiveController] = useState<AbortController | null>(null);
  const [streamStartedAt, setStreamStartedAt] = useState<number | null>(null);
  const [tokenPanelOpen, setTokenPanelOpen] = useState(false);
  const [tokenInput, setTokenInput] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const active = conversations.find((item) => item.id === activeId) ?? conversations[0];
  const messages = active.messages;

  const isStreaming = Boolean(activeController);
  const canSubmit = draft.trim().length > 0 && !isStreaming;

  const completedCount = useMemo(
    () =>
      messages.filter(
        (message) => message.role === "assistant" && message.status === "done",
      ).length,
    [messages],
  );

  // 会话变化即持久化；流式中的中间态每秒也会触发保存，代价可接受
  useEffect(() => {
    saveConversations(conversations);
  }, [conversations]);

  // 顶部实时计时：流式期间每秒刷新
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!isStreaming) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [isStreaming]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const patchActiveConversation = (
    updater: (conversation: Conversation) => Conversation,
  ) => {
    setConversations((current) =>
      current.map((item) => (item.id === active.id ? updater(item) : item)),
    );
  };

  const startQuery = async (rawQuery = draft) => {
    const query = rawQuery.trim();
    if (!query || isStreaming) return;

    // 历史取自发起时刻已完结的消息，供后端理解指代式追问
    const history = messages.filter((message) => message.status !== "streaming");

    const userMessage: ChatMessage = {
      id: makeId(),
      role: "user",
      content: query,
      createdAt: Date.now(),
    };

    const assistantId = makeId();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "正在连接问数智能体...",
      createdAt: Date.now(),
      status: "streaming",
      steps: [],
    };

    const controller = new AbortController();
    setActiveController(controller);
    setStreamStartedAt(Date.now());
    setDraft("");
    patchActiveConversation((conversation) => ({
      ...conversation,
      title:
        conversation.messages.length === 0
          ? query.slice(0, 24)
          : conversation.title,
      updatedAt: Date.now(),
      messages: [...conversation.messages, userMessage, assistantMessage],
    }));

    const onEvent = (event: AgentEvent) => {
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id !== active.id
            ? conversation
            : {
                ...conversation,
                updatedAt: Date.now(),
                messages: conversation.messages.map((message) =>
                  message.id === assistantId ? applyEvent(message, event) : message,
                ),
              },
        ),
      );
    };

    try {
      await streamQuery(query, { history, signal: controller.signal, onEvent });
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id !== active.id
            ? conversation
            : {
                ...conversation,
                messages: conversation.messages.map((message) =>
                  message.id === assistantId && message.status === "streaming"
                    ? { ...message, status: "done", content: "流程已结束，后端未返回查询结果。" }
                    : message,
                ),
              },
        ),
      );
    } catch (error) {
      const isAbort = error instanceof DOMException && error.name === "AbortError";
      const isAuthError = error instanceof ApiError && error.status === 401;
      if (isAuthError) {
        setTokenPanelOpen(true);
      }
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id !== active.id
            ? conversation
            : {
                ...conversation,
                messages: conversation.messages.map((message) =>
                  message.id === assistantId
                    ? {
                        ...message,
                        status: isAbort ? "done" : "error",
                        content: isAbort ? "已停止本次查询。" : "无法连接问数接口。",
                        error: isAbort
                          ? undefined
                          : error instanceof Error
                            ? error.message
                            : String(error),
                      }
                    : message,
                ),
              },
        ),
      );
    } finally {
      setActiveController(null);
      setStreamStartedAt(null);
    }
  };

  const stopQuery = () => {
    activeController?.abort();
  };

  const retryMessage = (assistantMessageId: string) => {
    if (isStreaming) return;
    const index = messages.findIndex((message) => message.id === assistantMessageId);
    if (index < 0) return;
    // 找到该助手消息之前最近的一条用户提问，用同一问题重新发起
    for (let i = index - 1; i >= 0; i -= 1) {
      if (messages[i].role === "user") {
        void startQuery(messages[i].content);
        return;
      }
    }
  };

  const newConversation = () => {
    if (isStreaming) return;
    const conversation = createConversation();
    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
    setDraft("");
  };

  const deleteConversation = (id: string) => {
    if (isStreaming && id === active.id) return;
    setConversations((current) => {
      const rest = current.filter((item) => item.id !== id);
      const next = rest.length > 0 ? rest : [createConversation()];
      if (id === active.id) {
        setActiveId(next[0].id);
      }
      return next;
    });
  };

  const clearActiveConversation = () => {
    if (isStreaming) return;
    patchActiveConversation((conversation) => ({ ...conversation, messages: [] }));
    setDraft("");
  };

  const saveToken = () => {
    setApiToken(tokenInput.trim());
    setTokenPanelOpen(false);
  };

  const streamElapsed = streamStartedAt ? Math.round((now - streamStartedAt) / 1000) : 0;

  return (
    <div className="h-dvh overflow-hidden bg-parchment text-ink">
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(90deg,rgba(32,32,29,0.045)_1px,transparent_1px),linear-gradient(rgba(32,32,29,0.035)_1px,transparent_1px)] bg-[size:48px_48px]" />
      <div className="pointer-events-none fixed inset-0 grain" />

      <div className="relative grid h-full min-h-0 overflow-hidden lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="hidden min-h-0 border-r border-ink/10 bg-[#efe6d8]/85 backdrop-blur lg:flex lg:flex-col">
          <div className="border-b border-ink/10 px-5 py-5">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center bg-ink text-parchment">
                <BarChart3 className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <div className="text-base font-semibold tracking-[0.02em]">电商问数</div>
                <div className="text-xs text-ink/50">my-shopkeeper-agent</div>
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
            <button
              type="button"
              onClick={newConversation}
              disabled={isStreaming}
              className="flex h-11 w-full items-center justify-center gap-2 bg-ink text-sm font-semibold text-parchment transition hover:bg-soot disabled:cursor-not-allowed disabled:bg-ink/35"
            >
              <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
              新会话
            </button>

            <section>
              <div className="mb-2 flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">
                <History className="h-3.5 w-3.5" aria-hidden="true" />
                会话记录
              </div>
              <div className="space-y-1.5">
                {conversations.map((conversation) => (
                  <div
                    key={conversation.id}
                    className={cn(
                      "group flex items-center gap-1 border px-3 py-2.5 transition",
                      conversation.id === active.id
                        ? "border-moss/40 bg-white/75"
                        : "border-ink/10 bg-white/42 hover:bg-white/60",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => !isStreaming && setActiveId(conversation.id)}
                      disabled={isStreaming}
                      className="min-w-0 flex-1 text-left"
                    >
                      <div className="truncate text-sm text-ink/80">{conversation.title}</div>
                      <div className="mt-0.5 text-[11px] text-ink/40">
                        {conversation.messages.length} 条消息
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteConversation(conversation.id)}
                      disabled={isStreaming && conversation.id === active.id}
                      className="shrink-0 rounded-full p-1.5 text-ink/30 opacity-0 transition hover:bg-tomato/10 hover:text-tomato focus:opacity-100 group-hover:opacity-100 disabled:cursor-not-allowed"
                      title="删除会话"
                      aria-label="删除会话"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">
                样例
              </div>
              <div className="space-y-2">
                {examples.map((example) => (
                  <button
                    key={example}
                    type="button"
                    disabled={isStreaming}
                    onClick={() => startQuery(example)}
                    className="w-full border border-ink/10 bg-white/42 px-3 py-3 text-left text-sm leading-5 text-ink/75 transition hover:border-moss/35 hover:bg-white/75 disabled:cursor-not-allowed disabled:opacity-55"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </section>
          </div>

          <div className="border-t border-ink/10 p-4">
            <div className="grid gap-2 text-xs text-ink/55">
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2">
                  <Server className="h-3.5 w-3.5" aria-hidden="true" />
                  API
                </span>
                <span className="truncate font-mono">{API_BASE_URL || "同源"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-2">
                  <Activity className="h-3.5 w-3.5" aria-hidden="true" />
                  完成
                </span>
                <span>{completedCount}</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setTokenInput(getApiToken());
                  setTokenPanelOpen((open) => !open);
                }}
                className="flex items-center justify-between transition hover:text-ink"
              >
                <span className="inline-flex items-center gap-2">
                  <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
                  访问令牌
                </span>
                <span>{getApiToken() ? "已配置" : "未配置"}</span>
              </button>
              {tokenPanelOpen && (
                <div className="flex items-center gap-2 pt-1">
                  <input
                    value={tokenInput}
                    onChange={(event) => setTokenInput(event.target.value)}
                    placeholder="粘贴服务器 API_TOKEN"
                    className="min-w-0 flex-1 border border-ink/15 bg-white/70 px-2 py-1.5 text-xs outline-none focus:border-moss/40"
                  />
                  <button
                    type="button"
                    onClick={saveToken}
                    className="shrink-0 bg-ink px-2.5 py-1.5 text-xs font-semibold text-parchment transition hover:bg-soot"
                  >
                    保存
                  </button>
                </div>
              )}
            </div>
          </div>
        </aside>

        <main className="flex min-h-0 min-w-0 flex-col overflow-hidden">
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-ink/10 bg-parchment/88 px-4 backdrop-blur lg:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid h-9 w-9 shrink-0 place-items-center bg-moss text-white lg:hidden">
                <BarChart3 className="h-4 w-4" aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-ink">智能数据分析 Agent</div>
                <div className="truncate text-xs text-ink/45">FastAPI SSE / LangGraph</div>
              </div>
            </div>
            <button
              type="button"
              onClick={clearActiveConversation}
              disabled={messages.length === 0 || isStreaming}
              className={cn(
                "grid h-9 w-9 place-items-center rounded-full text-ink/55 transition hover:bg-ink/5 hover:text-ink disabled:cursor-not-allowed disabled:opacity-35",
              )}
              title="清空当前会话"
              aria-label="清空当前会话"
            >
              <Eraser className="h-4 w-4" aria-hidden="true" />
            </button>
          </header>

          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            {messages.length === 0 ? (
              <EmptyState examples={examples} onUseExample={(example) => setDraft(example)} />
            ) : (
              <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 lg:px-8">
                {messages.map((message) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    onRetry={
                      message.role === "assistant" && message.status === "error"
                        ? () => retryMessage(message.id)
                        : undefined
                    }
                  />
                ))}
              </div>
            )}
          </div>

          <div className="border-t border-ink/10 bg-[#efe6d8]/45 px-4 py-2 text-center text-xs text-ink/45">
            <span className="inline-flex items-center gap-2">
              <Leaf className="h-3.5 w-3.5 text-moss" aria-hidden="true" />
              {isStreaming
                ? `运行中 · 已 ${streamElapsed}s`
                : "就绪"}
            </span>
          </div>
          <Composer
            value={draft}
            disabled={!canSubmit}
            isStreaming={isStreaming}
            onChange={setDraft}
            onSubmit={() => startQuery()}
            onStop={stopQuery}
          />
        </main>
      </div>
    </div>
  );
}
