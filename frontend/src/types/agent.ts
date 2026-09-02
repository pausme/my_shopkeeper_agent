/**
 * 智能体类型定义
 * 定义问数智能体前端使用的 SSE 事件、流程步骤、聊天消息和会话类型
 */
export type ProgressStatus = "running" | "success" | "error";

export type ProgressEvent = {
  type: "progress";
  step: string;
  status: ProgressStatus;
};

export type ResultEvent = {
  type: "result";
  data: unknown;
};

export type ErrorEvent = {
  type: "error";
  message: string;
};

export type AgentEvent = ProgressEvent | ResultEvent | ErrorEvent;

export type StepState = {
  step: string;
  status: ProgressStatus;
  updatedAt: number;
  /** 步骤首次进入 running 的时间戳，用于展示步骤耗时 */
  startedAt?: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  status?: "streaming" | "done" | "error";
  steps?: StepState[];
  result?: unknown;
  error?: string;
};

export type Conversation = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
};
