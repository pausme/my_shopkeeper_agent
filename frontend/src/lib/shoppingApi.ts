/**
 * 导购接口客户端
 * 封装 /api/shopping/* 的 SSE 问答、会话、反馈与对比接口
 */
import type {
  ShoppingEvent,
  ShoppingSessionDetail,
  ShoppingSessionSummary,
} from "../types/shopping";
import { API_BASE_URL, authHeaders } from "./agentApiShared";

const NO_EVENT_TIMEOUT_MS = 10 * 60 * 1000;

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(authHeaders() as Record<string, string>),
  };
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message =
      (body as { detail?: string }).detail ?? `请求失败：HTTP ${response.status}`;
    throw new Error(message);
  }
  return body as T;
}

export async function streamShoppingQuery(
  payload: {
    query: string;
    session_id?: string;
    history?: Array<{ role: string; content: string }>;
    clarification_count?: number;
  },
  options: {
    signal?: AbortSignal;
    onEvent: (event: ShoppingEvent) => void;
  },
) {
  const response = await fetch(`${API_BASE_URL}/api/shopping/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...authHeaders(),
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`导购接口请求失败：HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let watchdog: number | undefined;

  const readWithTimeout = () =>
    Promise.race([
      reader.read(),
      new Promise<never>((_, reject) => {
        watchdog = window.setTimeout(() => {
          reject(new Error("导购响应超时（10 分钟未收到事件）。"));
        }, NO_EVENT_TIMEOUT_MS);
      }),
    ]);

  try {
    while (true) {
      const { value, done } = await readWithTimeout();
      if (watchdog !== undefined) {
        clearTimeout(watchdog);
        watchdog = undefined;
      }
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split(/\n\n/);
      buffer = chunks.pop() ?? "";
      for (const chunk of chunks) {
        const payload = chunk
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.replace(/^data:\s?/, ""))
          .join("\n")
          .trim();
        if (!payload) continue;
        try {
          options.onEvent(JSON.parse(payload) as ShoppingEvent);
        } catch {
          // 单条坏事件跳过，不中断整次流
        }
      }
    }
  } finally {
    if (watchdog !== undefined) {
      clearTimeout(watchdog);
    }
  }
}

export function fetchShoppingSessions(): Promise<ShoppingSessionSummary[]> {
  return requestJson("/api/shopping/sessions");
}

export function fetchShoppingSessionDetail(
  sessionId: string,
): Promise<ShoppingSessionDetail> {
  return requestJson(`/api/shopping/sessions/${sessionId}`);
}

export function sendShoppingFeedback(payload: {
  session_id: string;
  message_id?: string;
  feedback_type: string;
  product_id?: string;
  comment?: string;
}): Promise<{ ok: boolean }> {
  return requestJson("/api/shopping/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** 行为埋点上报（商品点击等），fire-and-forget */
export function sendShoppingEvent(payload: {
  session_id: string;
  message_id?: string;
  event_type: string;
  product_id?: string;
}): void {
  requestJson("/api/shopping/events", {
    method: "POST",
    body: JSON.stringify(payload),
  }).catch(() => {});
}
