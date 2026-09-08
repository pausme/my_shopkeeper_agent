/**
 * 关注与提醒 API 客户端（二期 S2）
 */
import { API_BASE_URL, authHeaders } from "./agentApiShared";

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...(init.headers ?? {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw Object.assign(
      new Error((body as { detail?: string }).detail ?? `请求失败：HTTP ${response.status}`),
      { status: response.status },
    );
  }
  return body as T;
}

export type WatchItem = {
  watch_id: string;
  product_id: string;
  product_title: string | null;
  target_price: number | null;
  current_price: number | null;
  status: string;
  created_at: number | null;
};

export type AlertItem = {
  alert_id: string;
  product_id: string;
  alert_price: number;
  alert_reason: string | null;
  alert_status: string;
  created_at: number | null;
};

export function fetchWatchlist(): Promise<{
  items: WatchItem[];
  recent_alerts: AlertItem[];
}> {
  return requestJson("/api/shopping/watchlist");
}

export function watchProduct(
  productId: string,
  targetPrice?: number,
): Promise<{ ok: boolean; created: boolean }> {
  return requestJson("/api/shopping/watchlist", {
    method: "POST",
    body: JSON.stringify({ product_id: productId, target_price: targetPrice ?? null }),
  });
}

export function unwatchProduct(productId: string): Promise<{ ok: boolean }> {
  return requestJson(`/api/shopping/watchlist/${productId}`, { method: "DELETE" });
}

/** 详情弹窗内查询当前是否已关注 */
export function isWatched(productId: string): Promise<boolean> {
  return fetchWatchlist()
    .then((d) => d.items.some((item) => item.product_id === productId))
    .catch(() => false);
}
