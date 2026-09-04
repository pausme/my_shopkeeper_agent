/**
 * PickMate AI 前端主组件（N1/N8 改版）
 * 导购工作台：首页（搜索前置+场景入口）与对话页，桌面 Web 优先
 */
import {
  Eraser,
  History,
  KeyRound,
  MessageSquarePlus,
  Scale,
  Settings,
  ShoppingBag,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { AuthDialog } from "./components/AuthDialog";
import { Composer } from "./components/Composer";
import { ComparisonTable } from "./components/ComparisonTable";
import { ProductCard } from "./components/ProductCard";
import { ProductDetailModal } from "./components/ProductDetailModal";
import { ShoppingHome } from "./components/ShoppingHome";
import { SkeletonCards } from "./components/SkeletonCards";
import { cn } from "./lib/format";
import {
  fetchShoppingSessionDetail,
  fetchShoppingSessions,
  sendShoppingEvent,
  sendShoppingFeedback,
  streamShoppingQuery,
} from "./lib/shoppingApi";
import { getApiToken, getJwt, getUsername, setApiToken, setJwt } from "./lib/agentApiShared";
import type { RecommendedProduct, ShoppingEvent, ShoppingMessage, ShoppingSessionSummary } from "./types/shopping";

function makeId() {
  return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

// N7.2 条件胶囊：从用户输入中提取的条件
function extractConditions(query: string): string[] {
  const conditions: string[] = [];
  const budget = query.match(/(?:预算|以内|以内)[^\d]{0,4}(\d{2,5})/);
  if (budget) conditions.push(`预算 ${budget[1]} 以内`);
  const categories = ["厨房小电器", "家居生活", "数码配件", "母婴用品", "空气炸锅", "破壁机", "豆浆机", "安全座椅", "奶瓶", "辅食机", "充电宝", "耳机", "落地灯", "枕头", "按摩仪"];
  for (const category of categories) {
    if (query.includes(category)) {
      conditions.push(category);
      break;
    }
  }
  const exclusion = query.match(/不要([^，。,.!！?？\s]{1,8})/);
  if (exclusion) conditions.push(`不要${exclusion[1]}`);
  return conditions;
}

export default function App() {
  const [view, setView] = useState<"home" | "chat">("home");
  const [shoppingMessages, setShoppingMessages] = useState<ShoppingMessage[]>([]);
  const [shoppingSessionId, setShoppingSessionId] = useState("");
  const [shoppingClarificationCount, setShoppingClarificationCount] = useState(0);
  const [shoppingSessions, setShoppingSessions] = useState<ShoppingSessionSummary[]>([]);
  const [draft, setDraft] = useState("");
  const [activeController, setActiveController] = useState<AbortController | null>(null);
  const [streamStartedAt, setStreamStartedAt] = useState<number | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tokenInput, setTokenInput] = useState("");
  const [authOpen, setAuthOpen] = useState(false);
  const [jwt, setJwtState] = useState(() => getJwt());
  const [username, setUsernameState] = useState(() => getUsername());
  const [detailProduct, setDetailProduct] = useState<RecommendedProduct | null>(null);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLDivElement | null>(null);

  const isStreaming = Boolean(activeController);
  const canSubmit = draft.trim().length > 0 && !isStreaming;
  const lastRecommendation = useMemo(
    () => [...shoppingMessages].reverse().find((m) => m.kind === "recommendation"),
    [shoppingMessages],
  );

  useEffect(() => {
    fetchShoppingSessions()
      .then(setShoppingSessions)
      .catch(() => setShoppingSessions([]));
  }, []);

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
  }, [shoppingMessages]);

  const patchLastShoppingAssistant = (
    updater: (message: ShoppingMessage) => ShoppingMessage,
  ) => {
    setShoppingMessages((current) => {
      const index = current.map((m) => m.role).lastIndexOf("assistant");
      if (index < 0) return current;
      const next = [...current];
      next[index] = updater(next[index]);
      return next;
    });
  };

  const startShoppingQuery = async (
    rawQuery = draft,
    options: { selectedProductIds?: string[] } = {},
  ) => {
    const query = rawQuery.trim();
    if (!query || isStreaming) return;

    const userMessage: ShoppingMessage = {
      id: makeId(),
      role: "user",
      kind: "text",
      content: query,
      createdAt: Date.now(),
    };
    const placeholder: ShoppingMessage = {
      id: makeId(),
      role: "assistant",
      kind: "progress",
      content: "正在理解你的需求...",
      createdAt: Date.now(),
      steps: [],
    };

    const controller = new AbortController();
    setActiveController(controller);
    setStreamStartedAt(Date.now());
    setDraft("");
    setView("chat");
    // findings #11：跳过类应答给出"沿用上一轮需求"的显式反馈
    const isSkip = ["跳过", "不确定", "不知道"].includes(query);
    const prepend: ShoppingMessage[] = isSkip
      ? [
          {
            id: makeId(),
            role: "assistant",
            kind: "notice",
            content: "已跳过追问，沿用上一轮需求继续推荐。",
            createdAt: Date.now(),
          },
        ]
      : [];
    setShoppingMessages((current) => [...current, ...prepend, userMessage, placeholder]);

    const history = shoppingMessages
      .filter((m) => m.kind === "text" || m.kind === "clarification" || m.kind === "recommendation")
      .map((m) => ({
        role: m.role,
        content: m.kind === "recommendation" ? m.content.slice(0, 200) : m.content,
      }))
      .slice(-6);

    const onEvent = (event: ShoppingEvent) => {
      if (event.type === "progress") {
        if (event.session_id && !shoppingSessionId) {
          setShoppingSessionId(event.session_id);
        }
        patchLastShoppingAssistant((message) => ({
          ...message,
          content: `正在执行：${event.step}`,
          steps: message.steps?.includes(event.step)
            ? message.steps
            : [...(message.steps ?? []), event.step],
        }));
        return;
      }

      if (event.type === "clarification") {
        setShoppingSessionId(event.session_id);
        setShoppingClarificationCount(event.clarification_count);
        patchLastShoppingAssistant((message) => ({
          ...message,
          kind: "clarification",
          content: event.question,
          options: event.options ?? [],
        }));
        return;
      }

      if (event.type === "recommendation") {
        setShoppingSessionId(event.session_id);
        patchLastShoppingAssistant((message) => ({
          ...message,
          kind: "recommendation",
          content: event.summary,
          products: event.recommended_products,
          nextQuestion: event.next_question,
          messageId: event.message_id,
        }));
        return;
      }

      if (event.type === "comparison") {
        if (event.table?.rows?.length > 0) {
          setShoppingMessages((current) => [
            ...current,
            {
              id: makeId(),
              role: "assistant",
              kind: "comparison",
              content: "",
              createdAt: Date.now(),
              comparison: event.table,
            },
          ]);
        }
        return;
      }

      if (event.type === "error") {
        patchLastShoppingAssistant((message) => ({
          ...message,
          kind: "error",
          content: "这次导购没有成功。",
          error: event.message,
        }));
      }
    };

    try {
      await streamShoppingQuery(
        {
          query,
          session_id: shoppingSessionId || undefined,
          history,
          clarification_count: shoppingClarificationCount,
          selected_product_ids: options.selectedProductIds,
        },
        { signal: controller.signal, onEvent },
      );
      patchLastShoppingAssistant((message) =>
        message.kind === "progress"
          ? { ...message, content: "流程已结束，未返回推荐结果。" }
          : message,
      );
    } catch (error) {
      const isAbort = error instanceof DOMException && error.name === "AbortError";
      // findings #8：401 自动打开设置面板，引导配置令牌或登录
      const errorStatus = (error as { status?: number }).status;
      if (errorStatus === 401) {
        setSettingsOpen(true);
      }
      patchLastShoppingAssistant((message) =>
        message.kind === "progress"
          ? {
              ...message,
              kind: "error",
              content: isAbort ? "已停止本次导购。" : "无法连接导购接口。",
              error: isAbort ? undefined : error instanceof Error ? error.message : String(error),
            }
          : message,
      );
    } finally {
      setActiveController(null);
      setStreamStartedAt(null);
      setCompareIds([]);
      fetchShoppingSessions()
        .then(setShoppingSessions)
        .catch(() => {});
    }
  };

  const handleShoppingFeedback = (
    feedbackType: string,
    productId: string,
    messageId: string,
  ) => {
    if (!shoppingSessionId) return;
    sendShoppingFeedback({
      session_id: shoppingSessionId,
      message_id: messageId || undefined,
      feedback_type: feedbackType,
      product_id: productId,
    }).catch(() => {});
  };

  const handleProductClick = (productId: string, action: string) => {
    if (!shoppingSessionId) return;
    sendShoppingEvent({
      session_id: shoppingSessionId,
      event_type: action === "impression" ? "product_impression" : "product_click",
      product_id: productId,
      event_data: { action },
    });
  };

  const handleOptionClick = (option: string) => {
    if (isStreaming) return;
    void startShoppingQuery(option);
  };

  const handleCompare = (productId: string) => {
    setCompareIds((current) =>
      current.includes(productId)
        ? current.filter((id) => id !== productId)
        : current.length >= 4
          ? current
          : [...current, productId],
    );
  };

  const handleAskAbout = (productId: string, title: string) => {
    if (isStreaming) return;
    void startShoppingQuery(`${title}（${productId}）值不值得买？帮我分析一下`);
  };

  const submitCompare = () => {
    if (compareIds.length < 2 || isStreaming) return;
    void startShoppingQuery(`帮我对比这 ${compareIds.length} 款商品`, {
      selectedProductIds: compareIds,
    });
  };

  const [loadedSessionTitle, setLoadedSessionTitle] = useState("");
  const loadShoppingSession = async (sessionId: string) => {
    if (isStreaming) return;
    try {
      const detail = await fetchShoppingSessionDetail(sessionId);
      setLoadedSessionTitle(
        shoppingSessions.find((s) => s.session_id === sessionId)?.title ||
          shoppingSessions.find((s) => s.session_id === sessionId)?.last_query ||
          "历史会话",
      );
      setShoppingSessionId(sessionId);
      setShoppingClarificationCount(0);
      setShoppingMessages(
        detail.messages.map((row) => {
          const rowWithHydration = row as {
            summary?: string;
            products?: RecommendedProduct[];
          };
          return {
            id: row.message_id,
            role: row.role === "user" ? "user" : "assistant",
            kind:
              row.message_type === "clarification"
                ? "clarification"
                : row.message_type === "recommendation"
                  ? "recommendation"
                  : "text",
            content: rowWithHydration.summary || row.content,
            products: rowWithHydration.products,
            messageId: row.message_id,
            createdAt: row.created_at ?? Date.now(),
          };
        }),
      );
      setView("chat");
    } catch {
      // 加载失败静默处理
    }
  };

  const newConsult = () => {
    if (isStreaming) return;
    setShoppingMessages([]);
    setShoppingSessionId("");
    setShoppingClarificationCount(0);
    setCompareIds([]);
    setDraft("");
    setView("home");
  };

  const stopQuery = () => activeController?.abort();

  const handleAuthed = (token: string, name: string) => {
    setJwt(token, name);
    setJwtState(token);
    setUsernameState(name);
    setAuthOpen(false);
  };

  const handleLogout = () => {
    setJwt("", "");
    setJwtState("");
    setUsernameState("");
  };

  const streamElapsed = streamStartedAt ? Math.round((now - streamStartedAt) / 1000) : 0;
  const conditions = useMemo(
    () => extractConditions(lastRecommendation?.content ?? "") || [],
    [lastRecommendation],
  );
  const quickFollowUps = ["有没有更便宜的", "只看评分最高的", "帮我比较前两个", "帮我总结避坑要点"];

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-subtle text-ink">
      {authOpen && (
        <AuthDialog onClose={() => setAuthOpen(false)} onAuthed={handleAuthed} />
      )}
      {detailProduct && (
        <ProductDetailModal product={detailProduct} onClose={() => setDetailProduct(null)} />
      )}

      {/* 顶部导航（N8.2） */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-white px-4 lg:px-6">
        <button
          type="button"
          onClick={newConsult}
          className="flex items-center gap-2"
          title="回到导购首页"
        >
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-white">
            <ShoppingBag className="h-4 w-4" aria-hidden="true" />
          </span>
          <span className="text-base font-bold text-ink">PickMate AI</span>
          <span className="hidden text-xs text-ink/40 sm:inline">电商商品决策助手</span>
        </button>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={newConsult}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm font-medium transition",
              view === "home" ? "bg-primary/10 text-primary" : "text-ink/60 hover:bg-subtle",
            )}
          >
            首页
          </button>
          <button
            type="button"
            onClick={() => setView("chat")}
            disabled={shoppingMessages.length === 0}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-35",
              view === "chat" ? "bg-primary/10 text-primary" : "text-ink/60 hover:bg-subtle",
            )}
          >
            当前会话
          </button>

          {/* 历史会话下拉（N8.1） */}
          <div className="group relative">
            <button
              type="button"
              className="rounded-lg px-3 py-1.5 text-sm font-medium text-ink/60 transition hover:bg-subtle"
            >
              <History className="inline h-3.5 w-3.5" aria-hidden="true" /> 历史
            </button>
            <div className="invisible absolute right-0 top-full z-40 mt-1 w-72 rounded-xl border border-line bg-white p-2 opacity-0 shadow-panel transition group-hover:visible group-hover:opacity-100">
              {shoppingSessions.length === 0 && (
                <div className="px-3 py-2 text-xs text-ink/40">暂无历史会话</div>
              )}
              {shoppingSessions.slice(0, 8).map((session) => (
                <button
                  key={session.session_id}
                  type="button"
                  onClick={() => loadShoppingSession(session.session_id)}
                  className="w-full rounded-lg px-3 py-2 text-left transition hover:bg-subtle"
                >
                  <div className="truncate text-sm text-ink/80">
                    {session.title || session.last_query || "未命名咨询"}
                  </div>
                  <div className="truncate text-[11px] text-ink/40">{session.last_query ?? ""}</div>
                </button>
              ))}
            </div>
          </div>

          {/* 设置（N8.4：令牌/登录收进设置） */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setSettingsOpen((open) => !open)}
              className="rounded-lg p-2 text-ink/55 transition hover:bg-subtle hover:text-ink"
              aria-label="设置"
            >
              <Settings className="h-4 w-4" aria-hidden="true" />
            </button>
            {settingsOpen && (
              <div className="absolute right-0 top-full z-40 mt-1 w-72 rounded-xl border border-line bg-white p-4 shadow-panel">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-sm font-semibold text-ink">设置</span>
                  <button
                    type="button"
                    onClick={() => setSettingsOpen(false)}
                    className="text-ink/40 transition hover:text-ink"
                    aria-label="关闭设置"
                  >
                    <X className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => (jwt ? handleLogout() : setAuthOpen(true))}
                  className="mb-3 w-full rounded-lg border border-line px-3 py-2 text-sm transition hover:border-primary/40 hover:text-primary"
                >
                  {jwt ? `已登录：${username}（退出）` : "登录 / 注册"}
                </button>
                <div className="text-xs text-ink/50">
                  <div className="mb-1.5 flex items-center gap-1.5 font-medium">
                    <KeyRound className="h-3 w-3" aria-hidden="true" />
                    访问令牌
                  </div>
                  <div className="flex gap-1.5">
                    <input
                      value={tokenInput}
                      onChange={(event) => setTokenInput(event.target.value)}
                      placeholder={getApiToken() ? "已配置" : "粘贴 API_TOKEN"}
                      className="min-w-0 flex-1 rounded-lg border border-line px-2.5 py-1.5 outline-none focus:border-primary/50"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setApiToken(tokenInput.trim());
                        setSettingsOpen(false);
                      }}
                      className="rounded-lg bg-primary px-3 text-xs font-semibold text-white transition hover:bg-primary-dark"
                    >
                      保存
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* 主体 */}
      {view === "home" ? (
        <main className="min-h-0 flex-1 overflow-y-auto">
          <ShoppingHome
            sessions={shoppingSessions}
            onSubmit={(query) => void startShoppingQuery(query)}
            onOpenSession={loadShoppingSession}
          />
        </main>
      ) : (
        <>
          <main ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
            {shoppingMessages.length === 0 ? (
              <div className="grid h-full place-items-center text-sm text-ink/40">
                开始你的第一次咨询吧
              </div>
            ) : (
              <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-6 lg:px-8">
                {shoppingMessages.map((message, index) => {
                  const isComparison = message.kind === "comparison";
                  const conclusion = isComparison
                    ? [...shoppingMessages.slice(0, index)]
                        .reverse()
                        .find((m) => m.kind === "recommendation")?.content
                    : undefined;
                  return (
                    <div key={message.id}>
                      <div className={cn("flex gap-3", message.role === "user" && "justify-end")}>
                        {message.role === "assistant" && (
                          <span className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary text-white">
                            <Sparkles className="h-4 w-4" aria-hidden="true" />
                          </span>
                        )}
                        <div className="min-w-0 max-w-[880px] flex-1">
                          {message.kind === "text" && message.role === "user" && (
                            <div className="inline-block rounded-xl2 bg-primary px-4 py-2.5 text-[15px] leading-6 text-white shadow-card">
                              {message.content}
                            </div>
                          )}
                          {(message.kind !== "text" || message.role !== "user") && (
                            <div
                              className={cn(
                                "rounded-xl2 border bg-white px-5 py-4 shadow-card",
                                message.kind === "error" && "border-risk/30 bg-risk/5",
                              )}
                            >
                              {/* findings：历史回放的推荐消息映射为 assistant+text，
                                  此前缺少该分支导致回放出现空气泡 */}
                              {message.kind === "text" && (
                                <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">
                                  {message.content}
                                </p>
                              )}

                              {message.kind === "clarification" && (
                                <div>
                                  <p className="flex items-start gap-2 text-[15px] leading-7 text-ink">
                                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-brass" />
                                    {message.content}
                                  </p>
                                  {message.options && message.options.length > 0 && (
                                    <div className="mt-3 flex flex-wrap gap-2">
                                      {message.options.map((option) => (
                                        <button
                                          key={option}
                                          type="button"
                                          onClick={() => handleOptionClick(option)}
                                          className="rounded-full border border-line bg-white px-3.5 py-1.5 text-xs font-semibold text-ink/75 transition hover:border-primary/50 hover:text-primary"
                                        >
                                          {option}
                                        </button>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}

                              {message.kind === "progress" && (
                                <div>
                                  <p className="text-sm text-ink/60">{message.content}</p>
                                  {message.steps && message.steps.length > 0 && (
                                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                                      {message.steps.map((step, stepIndex) => (
                                        <span key={step} className="inline-flex items-center gap-1.5">
                                          {stepIndex > 0 && <span className="h-3 w-px bg-line" />}
                                          <span
                                            className={cn(
                                              "rounded-full px-2 py-0.5 text-[11px]",
                                              stepIndex === message.steps!.length - 1
                                                ? "bg-primary/10 font-semibold text-primary"
                                                : "bg-subtle text-ink/45",
                                            )}
                                          >
                                            {step}
                                          </span>
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                  <div className="mt-3">
                                    <SkeletonCards />
                                  </div>
                                </div>
                              )}

                              {message.kind === "notice" && (
                                <p className="text-xs leading-5 text-ink/50">{message.content}</p>
                              )}

                              {message.kind === "error" && (
                                <p className="text-sm text-risk">
                                  {message.content}
                                  {message.error ? `：${message.error}` : ""}
                                </p>
                              )}

                              {message.kind === "recommendation" && (
                                <div>
                                  <p className="text-[15px] leading-7 text-ink">{message.content}</p>
                                  {message.products && message.products.length > 0 && (
                                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                                      {message.products.map((product) => (
                                        <ProductCard
                                          key={product.product_id}
                                          product={product}
                                          onFeedback={(feedbackType, productId) =>
                                            handleShoppingFeedback(
                                              feedbackType,
                                              productId,
                                              message.messageId ?? "",
                                            )
                                          }
                                          onProductClick={(productId, action) =>
                                            handleProductClick(productId, action)
                                          }
                                          onDetail={(productId) => {
                                            const target = message.products?.find(
                                              (item) => item.product_id === productId,
                                            );
                                            if (target) setDetailProduct(target);
                                          }}
                                          onCompare={handleCompare}
                                          onAsk={handleAskAbout}
                                          inCompare={compareIds.includes(product.product_id)}
                                        />
                                      ))}
                                    </div>
                                  )}
                                  {message.nextQuestion && (
                                    <p className="mt-3 border-l-2 border-primary/40 pl-2 text-xs leading-5 text-ink/60">
                                      可以继续告诉我：{message.nextQuestion}
                                    </p>
                                  )}
                                </div>
                              )}

                              {message.kind === "comparison" && message.comparison && (
                                <ComparisonTable
                                  headers={message.comparison.headers}
                                  rows={message.comparison.rows}
                                  conclusion={conclusion}
                                />
                              )}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* 推荐后的快捷追问（N7.3） */}
                      {message.kind === "recommendation" &&
                        index === shoppingMessages.length - 1 &&
                        !isStreaming && (
                          <div className="mt-2 flex flex-wrap gap-1.5 pl-12">
                            {quickFollowUps.map((chip) => (
                              <button
                                key={chip}
                                type="button"
                                onClick={() => void startShoppingQuery(chip)}
                                className="rounded-full border border-line bg-white px-3 py-1 text-xs text-ink/60 transition hover:border-primary/45 hover:text-primary"
                              >
                                {chip}
                              </button>
                            ))}
                          </div>
                        )}
                    </div>
                  );
                })}
              </div>
            )}
          </main>

          {/* 条件胶囊（N7.2） */}
          {conditions.length > 0 && (
            <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-t border-line bg-white px-4 py-1.5 text-[11px] lg:px-8">
              <span className="text-ink/40">当前条件</span>
              {conditions.map((condition) => (
                <span
                  key={condition}
                  className="inline-flex items-center gap-1 rounded-full bg-primary/8 px-2 py-0.5 text-primary"
                >
                  {condition}
                </span>
              ))}
            </div>
          )}

          {/* 对比托盘（N4.7 加入对比） */}
          {compareIds.length > 0 && (
            <div className="flex shrink-0 items-center gap-2 border-t border-line bg-white px-4 py-2 lg:px-8">
              <Scale className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
              <span className="text-xs text-ink/60">对比栏（{compareIds.length}/4）</span>
              {compareIds.map((id) => (
                <span
                  key={id}
                  className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary"
                >
                  {id}
                  <button
                    type="button"
                    onClick={() => handleCompare(id)}
                    aria-label={`移除 ${id}`}
                    className="transition hover:text-risk"
                  >
                    <X className="h-2.5 w-2.5" aria-hidden="true" />
                  </button>
                </span>
              ))}
              <button
                type="button"
                onClick={submitCompare}
                disabled={compareIds.length < 2 || isStreaming}
                className="ml-auto rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-40"
              >
                开始对比
              </button>
            </div>
          )}
        </>
      )}

      {/* 状态栏 + 输入区 */}
      <div className="border-t border-line bg-white px-4 py-1.5 text-center text-xs text-ink/40">
        {isStreaming ? `导购运行中 · 已 ${streamElapsed}s` : "就绪"}
      </div>
      <div ref={composerRef}>
        <Composer
          value={draft}
          disabled={!canSubmit}
          isStreaming={isStreaming}
          onChange={setDraft}
          onSubmit={() => void startShoppingQuery()}
          onStop={stopQuery}
          placeholder="描述你的购买需求，例如：想买个空气炸锅预算 500..."
        />
      </div>

      {/* 悬浮操作：新咨询 / 清空（在对话视图中） */}
      {view === "chat" && shoppingMessages.length > 0 && !isStreaming && (
        <button
          type="button"
          onClick={newConsult}
          className="fixed bottom-28 right-6 z-30 inline-flex items-center gap-1.5 rounded-full bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-panel transition hover:bg-primary-dark"
        >
          <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
          新咨询
          <Eraser className="ml-1 h-3 w-3 opacity-60" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
