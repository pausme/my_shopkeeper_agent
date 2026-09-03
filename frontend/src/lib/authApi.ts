/**
 * 认证与会话同步客户端
 * JWT 登录/注册、会话列表的服务端读写
 */
import type { Conversation } from "../types/agent";
import { API_BASE_URL, authHeaders, getApiToken } from "./agentApiShared";

async function requestJson(path: string, init: RequestInit = {}) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(authHeaders() as Record<string, string>),
  };
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message =
      (body as { detail?: string }).detail ?? `请求失败：HTTP ${response.status}`;
    throw Object.assign(new Error(message), { status: response.status });
  }
  return body;
}

export type AuthResult = { token: string; username: string };

export function login(username: string, password: string): Promise<AuthResult> {
  return requestJson("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function register(
  username: string,
  password: string,
): Promise<AuthResult> {
  return requestJson("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function fetchConversations(): Promise<Conversation[]> {
  return requestJson("/api/conversations");
}

export function saveConversation(conversation: Conversation): Promise<unknown> {
  return requestJson(`/api/conversations/${conversation.id}`, {
    method: "PUT",
    body: JSON.stringify({
      id: conversation.id,
      title: conversation.title,
      messages: conversation.messages,
    }),
  });
}

export function deleteConversationRemote(id: string): Promise<unknown> {
  return requestJson(`/api/conversations/${id}`, { method: "DELETE" });
}

/** /api/query 仍使用共享令牌；导出供 App 判断是否已配置 */
export function hasApiToken() {
  return Boolean(getApiToken());
}
