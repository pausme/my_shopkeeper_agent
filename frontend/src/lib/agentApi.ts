/**
 * 智能体接口客户端
 * 封装后端 /api/query SSE 流式接口请求与事件解析逻辑
 * 附带：多轮 history 上送、访问令牌注入、无事件看门狗超时
 */
import type { AgentEvent, ChatMessage } from "../types/agent";
import { getApiToken } from "./storage";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

// 后端单次查询可能需要分钟级等待，但长时间收不到任何事件视为链路异常
const NO_EVENT_TIMEOUT_MS = 10 * 60 * 1000;

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

type QueryOptions = {
  history?: ChatMessage[];
  signal?: AbortSignal;
  onEvent: (event: AgentEvent) => void;
};

export async function streamQuery(query: string, options: QueryOptions) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  const token = getApiToken();
  if (token) {
    headers["X-API-Token"] = token;
  }

  // 只上送最近 6 条已完结消息（约 3 轮），让后端能理解指代式追问
  const history = (options.history ?? [])
    .filter((message) => message.status !== "streaming")
    .slice(-6)
    .map((message) => ({ role: message.role, content: message.content }));

  const response = await fetch(`${API_BASE_URL}/api/query`, {
    method: "POST",
    headers,
    body: JSON.stringify({ query, history }),
    signal: options.signal,
  });

  if (response.status === 401) {
    throw new ApiError("接口需要有效的访问令牌。", 401);
  }
  if (!response.ok) {
    throw new ApiError(`接口请求失败：HTTP ${response.status}`);
  }

  if (!response.body) {
    throw new Error("浏览器未返回可读取的流式响应。");
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
          reject(new Error("等待响应超时（10 分钟未收到任何事件），已停止本次查询。"));
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
        const event = parseSseChunk(chunk);
        if (event) {
          options.onEvent(event);
        }
      }
    }
  } finally {
    if (watchdog !== undefined) {
      clearTimeout(watchdog);
    }
  }

  buffer += decoder.decode();
  const tail = parseSseChunk(buffer);
  if (tail) {
    options.onEvent(tail);
  }
}

function parseSseChunk(chunk: string): AgentEvent | null {
  const payload = chunk
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace(/^data:\s?/, ""))
    .join("\n")
    .trim();

  if (!payload) return null;

  try {
    return JSON.parse(payload) as AgentEvent;
  } catch {
    return {
      type: "error",
      message: `无法解析后端事件：${payload}`,
    };
  }
}
