/**
 * 认证客户端
 * 用户名密码注册/登录，JWT 存于 localStorage
 */
import { API_BASE_URL, authHeaders } from "./agentApiShared";

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
