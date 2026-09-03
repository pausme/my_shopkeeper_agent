/**
 * API 客户端共享常量与请求头
 * 从 agentApi / authApi 共同引用，避免循环依赖
 */

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

const TOKEN_KEY = "shopkeeper.apiToken";
const JWT_KEY = "shopkeeper.jwt";
const USERNAME_KEY = "shopkeeper.username";

export function getApiToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setApiToken(token: string) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // 忽略私有模式等写入失败
  }
}

export function getJwt(): string {
  try {
    return localStorage.getItem(JWT_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setJwt(jwt: string, username: string) {
  try {
    if (jwt) {
      localStorage.setItem(JWT_KEY, jwt);
      localStorage.setItem(USERNAME_KEY, username);
    } else {
      localStorage.removeItem(JWT_KEY);
      localStorage.removeItem(USERNAME_KEY);
    }
  } catch {
    // 忽略写入失败
  }
}

export function getUsername(): string {
  try {
    return localStorage.getItem(USERNAME_KEY) ?? "";
  } catch {
    return "";
  }
}

/** 组装需要携带的鉴权请求头：共享令牌（API_TOKEN）+ JWT（用户登录） */
export function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const apiToken = getApiToken();
  if (apiToken) {
    headers["X-API-Token"] = apiToken;
  }
  const jwt = getJwt();
  if (jwt) {
    headers["Authorization"] = `Bearer ${jwt}`;
  }
  return headers;
}
