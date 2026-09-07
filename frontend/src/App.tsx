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
  SlidersHorizontal,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { AuthDialog } from "./components/AuthDialog";
import { Composer } from "./components/Composer";
import { ComparisonTable } from "./components/ComparisonTable";
import {
  applyFilters,
  EMPTY_FILTERS,
  FilterPanel,
  type ResultFilters,
} from "./components/FilterPanel";
import { ProductCard } from "./components/ProductCard";
import { ProductDetailModal } from "./components/ProductDetailModal";
import { ShoppingHome } from "./components/ShoppingHome";
import { SkeletonCards } from "./components/SkeletonCards";
import { cn } from "./lib/format";
import {
  deleteShoppingSessionRemote,
  stopShoppingSession,
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
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historySearch, setHistorySearch] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [loadingSessionId, setLoadingSessionId] = useState("");
  // N8.3 结果筛选面板
  const [filterOpen, setFilterOpen] = useState(false);
  const [resultFilters, setResultFilters] = useState<ResultFilters>(EMPTY_FILTERS);
  const [tokenInput, setTokenInput] = useState("");
  const [authOpen, setAuthOpen] = useState(false);
  const [jwt, setJwtState] = useState(() => getJwt());
  const [username, setUsernameState] = useState(() => getUsername());
  const [detailProduct, setDetailProduct] = useState<RecommendedProduct | null>(null);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [sessionLoadError, setSessionLoadError] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLDivElement | null>(null);

  const isStreaming = Boolean(activeController);
  const canSubmit = draft.trim().length > 0 && !isStreaming;
  const lastRecommendation = useMemo(
    () => [...shoppingMessages].reverse().find((m) => m.kind === "recommendation"),
    [shoppingMessages],
  );
  const productTitleById = useMemo(() => {
    const titles = new Map<string, string>();
    for (const message of shoppingMessages) {
      for (const product of message.products ?? []) {
        titles.set(product.product_id, product.title);
      }
    }
    return titles;
  }, [shoppingMessages]);

  useEffect(() => {
    setShoppingSessions([]);
    fetchShoppingSessions()
      .then(setShoppingSessions)
      .catch(() => setShoppingSessions([]));
  }, [jwt]);

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
    setSessionLoadError("");

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
        const stepLabel = STEP_LABELS[event.step] ?? event.step;
        patchLastShoppingAssistant((message) => ({
          ...message,
          content: `正在${stepLabel}...`,
          steps: message.steps?.includes(stepLabel)
            ? message.steps
            : [...(message.steps ?? []), stepLabel],
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

  const handleAskAbout = (_productId: string, title: string) => {
    if (isStreaming) return;
    void startShoppingQuery(`${title} 值不值得买？帮我分析一下`);
  };

  const submitCompare = () => {
    if (compareIds.length < 2 || isStreaming) return;
    void startShoppingQuery(`帮我对比这 ${compareIds.length} 款商品`, {
      selectedProductIds: compareIds,
    });
  };

  const [loadedSessionTitle, setLoadedSessionTitle] = useState("");
  // N11.7：历史项删除（属主校验由后端保证，匿名会话仅共享令牌持有者可删）
  const handleDeleteSession = async (sessionId: string) => {
    // findings #20：删除需确认，失败给出提示
    if (!window.confirm("确定删除这条咨询记录吗？删除后不可恢复。")) return;
    try {
      await deleteShoppingSessionRemote(sessionId);
      setShoppingSessions((current) => current.filter((s) => s.session_id !== sessionId));
      if (sessionId === shoppingSessionId) {
        setShoppingSessionId("");
        setShoppingMessages([]);
        setLoadedSessionTitle("");
      }
    } catch {
      setHistoryError("删除失败：可能无权限或会话已不存在");
      window.setTimeout(() => setHistoryError(""), 3000);
    }
  };

  const loadShoppingSession = async (sessionId: string) => {
    if (isStreaming) return;
    setLoadingSessionId(sessionId);
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
      setShoppingSessions((current) =>
        current.filter((session) => session.session_id !== sessionId),
      );
      setSessionLoadError("该会话不属于当前账号或已删除");
      setHistoryError("该会话不属于当前账号或已删除");
      window.setTimeout(() => setHistoryError(""), 3000);
      setView("home");
    } finally {
      setLoadingSessionId("");
    }
  };

  const newConsult = () => {
    if (isStreaming) return;
    setShoppingMessages([]);
    setShoppingSessionId("");
    setShoppingClarificationCount(0);
    setCompareIds([]);
    setDraft("");
    setLoadedSessionTitle("");
    setSessionLoadError("");
    setView("home");
  };

  const stopQuery = () => {
    activeController?.abort();
    // F-REG-004：同步标记服务端会话状态为 stopped
    if (shoppingSessionId) stopShoppingSession(shoppingSessionId);
  };

  const handleAuthed = (token: string, name: string) => {
    setJwt(token, name);
    setJwtState(token);
    setUsernameState(name);
    setShoppingMessages([]);
    setShoppingSessionId("");
    setShoppingClarificationCount(0);
    setShoppingSessions([]);
    setCompareIds([]);
    setLoadedSessionTitle("");
    setSessionLoadError("");
    setView("home");
    setAuthOpen(false);
  };

  const handleLogout = () => {
    setJwt("", "");
    setJwtState("");
    setUsernameState("");
    setShoppingMessages([]);
    setShoppingSessionId("");
    setShoppingClarificationCount(0);
    setShoppingSessions([]);
    setCompareIds([]);
    setLoadedSessionTitle("");
    setSessionLoadError("");
    setView("home");
  };

  const streamElapsed = streamStartedAt ? Math.round((now - streamStartedAt) / 1000) : 0;
  const conditions = useMemo(
    () => extractConditions(lastRecommendation?.content ?? "") || [],
    [lastRecommendation],
  );
  const quickFollowUps = ["有没有更便宜的", "只看评分最高的", "帮我比较前两个", "帮我总结避坑要点"];
  // N8.3：筛选只作用于最新一次推荐的商品卡
  const lastRecommendationId = lastRecommendation?.id;
  const filteredProducts = useMemo(
    () =>
      lastRecommendation ? applyFilters(lastRecommendation.products ?? [], resultFilters) : [],
    [lastRecommendation, resultFilters],
  );

// N11.9 过程文案用户友好化：研发术语 -> 用户视角
const STEP_LABELS: Record<string, string> = {
  理解需求: "理解你的需求",
  改写追问: "整理你的问题",
  判断是否追问: "确认需求是否完整",
  召回商品: "筛选候选商品",
  分析评价: "分析评价与风险",
  商品排序: "综合比较候选",
  生成推荐: "整理推荐理由",
};

// N11.6 标题兜底：过短/纯数字标题不可用
function displayTitle(title: string | null | undefined, fallback: string | null | undefined): string {
  const t = (title ?? "").trim();
  if (t.length >= 4 && !/^\d+$/.test(t)) return t;
  const f = (fallback ?? "").trim();
  if (f.length >= 4 && !/^\d+$/.test(f)) return f.slice(0, 24);
  return "导购咨询";
}

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-subtle text-ink">
      {authOpen && (
        <AuthDialog onClose={() => setAuthOpen(false)} onAuthed={handleAuthed} />
      )}
      {detailProduct && (
        <ProductDetailModal
          product={detailProduct}
          onClose={() => setDetailProduct(null)}
          onCompare={handleCompare}
          onAsk={(productId, title) => {
            const question = `${title}值不值得买？帮我分析下`;
            void startShoppingQuery(question);
          }}
        />
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
          {/* N11.4：无会话时隐藏"当前会话"，避免不可点的禁用态 */}
          {shoppingMessages.length > 0 && (
            <button
              type="button"
              onClick={() => setView("chat")}
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium transition",
                view === "chat" ? "bg-primary/10 text-primary" : "text-ink/60 hover:bg-subtle",
              )}
            >
              当前会话
            </button>
          )}

          {/* 历史会话下拉（N8.1；N11.7 hover 改点击展开，点外部关闭） */}
          <div className="relative">
            <button
              type="button"
              onClick={() => {
                setSettingsOpen(false);
                setHistoryOpen((open) => !open);
              }}
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium text-ink/60 transition hover:bg-subtle",
                historyOpen && "bg-subtle text-ink",
              )}
            >
              <History className="inline h-3.5 w-3.5" aria-hidden="true" /> 历史
            </button>
            {historyOpen && (
              <div
                className="fixed inset-0 z-30"
                onClick={() => setHistoryOpen(false)}
                aria-hidden="true"
              />
            )}
            <div
              className={cn(
                "absolute right-0 top-full z-40 mt-1 w-72 rounded-xl border border-line bg-white p-2 shadow-panel transition",
                historyOpen ? "visible opacity-100" : "invisible opacity-0",
              )}
            >
              {historyError && (
                <div className="mb-1.5 rounded-lg bg-risk/8 px-2.5 py-1.5 text-[11px] text-risk">
                  {historyError}
                </div>
              )}
              {shoppingSessions.length > 3 && (
                <input
                  value={historySearch}
                  onChange={(event) => setHistorySearch(event.target.value)}
                  placeholder="搜索历史会话..."
                  className="mb-1.5 w-full rounded-lg border border-line px-2.5 py-1.5 text-xs outline-none focus:border-primary/50"
                />
              )}
              {(() => {
                const keyword = historySearch.trim();
                const filtered = keyword
                  ? shoppingSessions.filter(
                      (s) =>
                        (s.title ?? "").includes(keyword) ||
                        (s.last_query ?? "").includes(keyword),
                    )
                  : shoppingSessions;
                if (filtered.length === 0) {
                  return (
                    <div className="px-3 py-3 text-xs text-ink/40">
                      {shoppingSessions.length === 0 ? "暂无历史会话" : "没有匹配的会话"}
                      {shoppingSessions.length === 0 && (
                        <div className="mt-2">
                          <button
                            type="button"
                            onClick={() => setHistoryOpen(false)}
                            className="rounded-md border border-line px-2 py-1 text-[11px] text-ink/60 transition hover:border-primary/40 hover:text-primary"
                          >
                            去发起第一次咨询
                          </button>
                        </div>
                      )}
                    </div>
                  );
                }
                return filtered.slice(0, 10).map((session) => (
                  <div
                    key={session.session_id}
                    className="group/item flex items-center gap-1 rounded-lg px-2 transition hover:bg-subtle"
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setHistoryOpen(false);
                        loadShoppingSession(session.session_id);
                      }}
                      disabled={loadingSessionId === session.session_id}
                      className="min-w-0 flex-1 py-2 text-left disabled:opacity-50"
                    >
                      <div className="truncate text-sm text-ink/80">
                        {displayTitle(session.title, session.last_query)}
                      </div>
                      <div className="truncate text-[11px] text-ink/40">
                        {loadingSessionId === session.session_id
                          ? "加载中..."
                          : (session.last_query ?? "")}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteSession(session.session_id)}
                      aria-label="删除该会话"
                      className="shrink-0 rounded-md p-1.5 text-ink/30 opacity-0 transition hover:bg-risk/10 hover:text-risk group-hover/item:opacity-100"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </div>
                ));
              })()}
            </div>
          </div>

          {/* 设置（N8.4：令牌/登录收进设置） */}
          <div className="relative">
            <button
              type="button"
              onClick={() => {
                setHistoryOpen(false);
                setSettingsOpen((open) => !open);
              }}
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
                {/* N11.5：访问令牌属于开发者配置，折叠进"高级设置"，普通 C 端无感知 */}
                <details className="text-xs text-ink/50">
                  <summary className="cursor-pointer font-medium text-ink/45 transition hover:text-ink/70">
                    高级设置
                  </summary>
                  <div className="mt-2">
                    <div className="mb-1.5 flex items-center gap-1.5 font-medium">
                      <KeyRound className="h-3 w-3" aria-hidden="true" />
                      访问令牌（仅特殊部署需要）
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
                </details>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* 主体 */}
      {view === "home" ? (
        <main className="min-h-0 flex-1 overflow-y-auto">
          {sessionLoadError && (
            <div className="mx-auto mt-4 max-w-3xl rounded-lg border border-risk/25 bg-risk/5 px-4 py-2 text-sm text-risk">
              {sessionLoadError}
            </div>
          )}
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
              <div className="grid h-full place-items-center gap-3">
                <span className="text-sm text-ink/40">这里还没有对话</span>
                <button
                  type="button"
                  onClick={newConsult}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary-dark"
                >
                  回到首页发起咨询
                </button>
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
                                      {(message.id === lastRecommendationId
                                        ? filteredProducts
                                        : message.products
                                      ).map((product) => (
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

                      {/* N8.3：最新推荐的筛选入口 + 筛尽提示 */}
                      {message.kind === "recommendation" &&
                        message.id === lastRecommendationId &&
                        !isStreaming && (
                          <div className="relative mt-2 pl-12">
                            <button
                              type="button"
                              onClick={() => setFilterOpen((open) => !open)}
                              className="inline-flex items-center gap-1 rounded-full border border-line bg-white px-3 py-1 text-xs text-ink/60 transition hover:border-primary/45 hover:text-primary"
                            >
                              <SlidersHorizontal className="h-3 w-3" aria-hidden="true" />
                              筛选本次推荐
                            </button>
                            {filteredProducts.length === 0 && (
                              <span className="ml-2 text-xs text-risk">
                                当前筛选条件下没有商品，试试放宽条件或重新推荐
                              </span>
                            )}
                            <FilterPanel
                              open={filterOpen}
                              onClose={() => setFilterOpen(false)}
                              products={message.products ?? []}
                              filters={resultFilters}
                              onChange={setResultFilters}
                              baseQuery={
                                [...shoppingMessages.slice(0, index)]
                                  .reverse()
                                  .find((m) => m.role === "user")?.content ?? ""
                              }
                              onRequery={(query) => {
                                setFilterOpen(false);
                                void startShoppingQuery(query);
                              }}
                            />
                          </div>
                        )}

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

        </>
      )}

      {/* 状态栏 + 输入区（N11.1/3：仅对话页显示，首页只有中部搜索一个入口） */}
      {view === "chat" && (
        <>
          <div className="flex shrink-0 flex-wrap items-center gap-2 border-t border-line bg-white px-4 py-1.5 text-xs text-ink/40 lg:px-8">
            <span className="shrink-0">
              {isStreaming ? `导购运行中 · 已 ${streamElapsed}s` : "就绪"}
            </span>
            {compareIds.length > 0 && (
              <>
                <span className="h-3 w-px bg-line" />
                <Scale className="h-3 w-3 shrink-0 text-primary" aria-hidden="true" />
                {compareIds.map((id, index) => {
                  const productName = productTitleById.get(id) ?? `商品${index + 1}`;
                  return (
                    <span
                      key={id}
                      className="inline-flex max-w-36 items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary"
                    >
                      <span className="truncate">{productName}</span>
                      <button
                        type="button"
                        onClick={() => handleCompare(id)}
                        aria-label={`移除 ${productName}`}
                        className="shrink-0 transition hover:text-risk"
                      >
                        <X className="h-2.5 w-2.5" aria-hidden="true" />
                      </button>
                    </span>
                  );
                })}
                <button
                  type="button"
                  onClick={submitCompare}
                  disabled={compareIds.length < 2 || isStreaming}
                  className="ml-auto shrink-0 rounded-lg bg-primary px-3 py-1 text-[11px] font-semibold text-white transition hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-40"
                >
                  开始对比（{compareIds.length}/4）
                </button>
              </>
            )}
          </div>
          <div ref={composerRef}>
            <Composer
              value={draft}
              disabled={!canSubmit}
              isStreaming={isStreaming}
              onChange={setDraft}
              onSubmit={() => void startShoppingQuery()}
              onStop={stopQuery}
              placeholder="继续描述你的需求，例如：有没有更便宜的..."
            />
          </div>
        </>
      )}

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
