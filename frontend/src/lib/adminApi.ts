/**
 * 商品数据管理台客户端（J3）
 * 对接 /api/admin/*：商品列表/编辑/软删、评价样本、风险摘要、重建索引
 */
import { API_BASE_URL, authHeaders } from "./agentApiShared";

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
    throw Object.assign(new Error(message), { status: response.status });
  }
  return body as T;
}

export type AdminProduct = {
  product_id: string;
  title: string;
  category_name: string;
  brand: string | null;
  price: number;
  promotion_price: number | null;
  stock: number | null;
  sales_30d: number | null;
  rating: number;
  review_count: number | null;
  status: string;
  image_url?: string | null;
  updated_at?: string | null;
};

export function fetchAdminProducts(
  keyword: string,
  page: number,
): Promise<{ total: number; items: AdminProduct[] }> {
  return requestJson(
    `/api/admin/products?keyword=${encodeURIComponent(keyword)}&page=${page}`,
  );
}

export function patchAdminProduct(
  productId: string,
  fields: Partial<Pick<AdminProduct, "title" | "brand" | "price" | "promotion_price" | "stock" | "sales_30d" | "status">>,
): Promise<{ ok: boolean; product: AdminProduct }> {
  return requestJson(`/api/admin/products/${productId}`, {
    method: "PATCH",
    body: JSON.stringify(fields),
  });
}

export function deleteAdminProduct(productId: string): Promise<{ ok: boolean }> {
  return requestJson(`/api/admin/products/${productId}`, { method: "DELETE" });
}

export function fetchProductReviews(
  productId: string,
): Promise<{ items: Array<{ review_id: string; rating: number; content: string; sentiment: string | null }> }> {
  return requestJson(`/api/admin/products/${productId}/reviews`);
}

export function patchRiskSummary(
  productId: string,
  fields: Partial<{
    risk_level: string;
    risk_summary: string;
    positive_summary: string;
    suitable_for: string;
    not_suitable_for: string;
  }>,
): Promise<{ ok: boolean }> {
  return requestJson(`/api/admin/products/${productId}/risk`, {
    method: "PATCH",
    body: JSON.stringify(fields),
  });
}

export function rebuildIndex(): Promise<{
  ok: boolean;
  products: number;
  reviews: number;
}> {
  return requestJson("/api/admin/rebuild-index", { method: "POST" });
}

// 后端 list_rules 将 value_json 扁平化进顶层：global → enabled/max_per_day，quiet_hours → start/end
export type AlertRule = {
  rule_key: string;
  description?: string | null;
  enabled?: boolean;
  max_per_day?: number;
  start?: string;
  end?: string;
};

export function fetchAlertRules(): Promise<{ items: AlertRule[] }> {
  return requestJson("/api/admin/alert-rules");
}

export function putAlertRule(rule: AlertRule): Promise<{ ok: boolean }> {
  // 后端契约：{rule_key, description, value_json}——其余扁平字段属于规则参数
  const { rule_key, description, ...value_json } = rule;
  return requestJson(`/api/admin/alert-rules/${rule_key}`, {
    method: "PUT",
    body: JSON.stringify({ rule_key, description, value_json }),
  });
}
