/**
 * 本地持久化工具
 * 会话列表存入 localStorage（刷新不丢），访问令牌单独存储
 */
import type { Conversation } from "../types/agent";

const CONVERSATIONS_KEY = "shopkeeper.conversations.v1";
const TOKEN_KEY = "shopkeeper.apiToken";

export function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(CONVERSATIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as Conversation[]) : [];
  } catch {
    return [];
  }
}

export function saveConversations(conversations: Conversation[]) {
  try {
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations));
  } catch {
    // 存储空间不足等异常时静默失败，会话仅退化为本次内存可见
  }
}

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
