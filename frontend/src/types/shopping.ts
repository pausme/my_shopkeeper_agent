/**
 * 导购（AI 商品决策助手）类型定义
 * 对应后端 /api/shopping/* 的 SSE 事件与页面数据结构
 */

export type ShoppingProgressEvent = {
  type: "progress";
  step: string;
  status: "running" | "success" | "error";
  session_id?: string;
};

export type ShoppingClarificationEvent = {
  type: "clarification";
  question: string;
  options: string[];
  session_id: string;
  clarification_count: number;
};

export type RecommendedProduct = {
  product_id: string;
  title: string;
  category_name: string;
  brand: string | null;
  price: number;
  promotion_price: number | null;
  rating: number;
  sales_30d: number | null;
  review_count?: number | null;
  attributes: Record<string, string>;
  semantic_score?: number;
  reason: string;
  /** 推荐结论：最推荐 / 预算优先 / 品质优先 / 谨慎购买（PRD 10.5） */
  verdict?: string;
  /** 到手价超出用户预算但优势明显被保留展示（PRD 10.4 显式标记） */
  budget_exceeded?: boolean;
};

export type ShoppingRecommendationEvent = {
  type: "recommendation";
  session_id: string;
  message_id: string;
  summary: string;
  next_question: string;
  recommended_products: RecommendedProduct[];
};

export type ShoppingComparisonEvent = {
  type: "comparison";
  session_id: string;
  table: { headers: string[]; rows: Array<Record<string, string>> };
};

export type ShoppingErrorEvent = {
  type: "error";
  message: string;
};

export type ShoppingEvent =
  | ShoppingProgressEvent
  | ShoppingClarificationEvent
  | ShoppingRecommendationEvent
  | ShoppingComparisonEvent
  | ShoppingErrorEvent;

/** 导购会话中的一条消息（前端渲染视图） */
export type ShoppingMessage = {
  id: string;
  role: "user" | "assistant";
  kind:
    | "text"
    | "clarification"
    | "recommendation"
    | "comparison"
    | "progress"
    | "notice"
    | "error";
  content: string;
  createdAt: number;
  /** recommendation 专属 */
  products?: RecommendedProduct[];
  nextQuestion?: string;
  messageId?: string;
  comparison?: ShoppingComparisonEvent["table"];
  /** progress 专属 */
  steps?: string[];
  error?: string;
  /** clarification 专属：快捷选项 */
  options?: string[];
};

export type ShoppingSessionSummary = {
  session_id: string;
  title: string | null;
  scene_tag: string | null;
  status: string;
  last_query: string | null;
  updated_at: number | null;
};

export type ShoppingSessionDetail = {
  session_id: string;
  messages: Array<{
    message_id: string;
    role: string;
    content: string;
    message_type: string;
    created_at: number | null;
  }>;
};
