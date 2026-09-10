/**
 * 商品数据管理台（J3，管理员专用）
 * 商品列表+搜索+编辑抽屉、评价样本、风险摘要编辑、一键重建索引
 * 通过 URL hash 路由 #admin 访问；非管理员后端 403 时显示提示
 */
import { Database, Loader2, RefreshCw, Save, Search, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useDrawerFocus } from "../lib/drawerFocus";
import {
  deleteAdminProduct,
  fetchAlertRules,
  putAlertRule,
  type AlertRule,
  fetchAdminProducts,
  fetchProductReviews,
  patchAdminProduct,
  patchRiskSummary,
  rebuildIndex,
  type AdminProduct,
} from "../lib/adminApi";

export function AdminConsole() {
  const [items, setItems] = useState<AdminProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  // N12.33：401/403 时展示明确的无权限空态（替代半可用的管理界面）
  const [deniedMessage, setDeniedMessage] = useState("");
  const [editing, setEditing] = useState<AdminProduct | null>(null);
  const [reviewsFor, setReviewsFor] = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState(false);
  const [tab, setTab] = useState<"products" | "rules">("products");
  const [rules, setRules] = useState<AlertRule[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminProducts(keyword, page);
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      const status = (err as { status?: number }).status;
      if (status === 401 || status === 403) {
        setDeniedMessage(
          status === 401
            ? "需要先登录管理员账号才能使用商品数据管理台。"
            : "你没有商品数据管理权限，请切换管理员账号后再进入。",
        );
        return;
      }
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [keyword, page]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (tab === "rules") {
      fetchAlertRules()
        .then((d) => setRules(d.items ?? []))
        .catch(() => setRules([]));
    }
  }, [tab]);

  const flash = (text: string) => {
    setNotice(text);
    window.setTimeout(() => setNotice(""), 4000);
  };

  /** 保存提醒规则：乐观更新本地，失败时回滚并提示 */
  const saveRule = async (next: AlertRule) => {
    const previous = rules;
    setRules((cur) => cur.map((r) => (r.rule_key === next.rule_key ? next : r)));
    try {
      await putAlertRule(next);
      flash("规则已保存（下次价格检查生效）");
    } catch (err) {
      setRules(previous);
      flash(`规则保存失败：${err instanceof Error ? err.message : "请重试"}`);
    }
  };

  const handleRebuild = async () => {
    if (!window.confirm("重建会全量刷新 Qdrant 向量与 ES 评价索引（约 10~30 秒），继续？")) return;
    setRebuilding(true);
    try {
      const result = await rebuildIndex();
      flash(`索引重建完成：商品 ${result.products} 款、评价 ${result.reviews} 条`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重建失败");
    } finally {
      setRebuilding(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm(`确认软删商品 ${id}？重建索引后将从推荐中移除。`)) return;
    try {
      await deleteAdminProduct(id);
      flash("已软删，记得重建索引生效");
      void load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / 20));

  // N12.33：无权限空态——不渲染任何管理操作，只说明原因并提供返回
  if (deniedMessage) {
    return (
      <div className="grid min-h-dvh place-items-center bg-subtle p-6">
        <div className="max-w-md rounded-xl2 border border-line bg-white p-8 text-center shadow-card">
          <Database className="mx-auto h-8 w-8 text-muted" aria-hidden="true" />
          <h1 className="mt-3 text-base font-semibold text-ink">商品数据管理台</h1>
          <p className="mt-2 text-sm leading-6 text-muted">{deniedMessage}</p>
          <a
            href="#/"
            className="mt-5 inline-flex h-10 items-center rounded-lg bg-primary px-5 text-sm font-semibold text-white transition hover:bg-primary-dark active:scale-[0.98]"
          >
            返回导购
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-dvh bg-subtle p-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="inline-flex items-center gap-2 text-lg font-bold text-ink">
            <Database className="h-5 w-5 text-primary" aria-hidden="true" />
            商品数据管理台
            <a href="#/" className="ml-2 text-xs font-normal text-ink/50 hover:text-primary">
              返回导购
            </a>
          </h1>
          <button
            type="button"
            onClick={() => void handleRebuild()}
            disabled={rebuilding}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white transition hover:bg-primary-dark disabled:opacity-50"
          >
            {rebuilding ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
            )}
            {rebuilding ? "重建中..." : "一键重建索引"}
          </button>
        </div>

        {notice && (
          <div className="mb-3 rounded-lg border border-good/30 bg-good/10 px-4 py-2 text-sm text-good">
            {notice}
          </div>
        )}
        {error && (
          <div className="mb-3 rounded-lg border border-risk/30 bg-risk/5 px-4 py-2 text-sm text-risk">
            {error}
          </div>
        )}

        {/* Tab 切换：商品管理 / 提醒规则（P2） */}
        <div className="mb-3 flex gap-1.5">
          <button
            type="button"
            onClick={() => setTab("products")}
            className={
              tab === "products"
                ? "rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-white"
                : "rounded-lg border border-line px-3 py-1.5 text-sm text-ink/60 hover:border-primary/40"
            }
          >
            商品管理
          </button>
          <button
            type="button"
            onClick={() => setTab("rules")}
            className={
              tab === "rules"
                ? "rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-white"
                : "rounded-lg border border-line px-3 py-1.5 text-sm text-ink/60 hover:border-primary/40"
            }
          >
            提醒规则
          </button>
        </div>

        {/* 搜索栏 */}
        <div className="mb-3 flex gap-2">
          <div className="relative flex-1">
            <Search
              className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/45"
              aria-hidden="true"
            />
            <input
              value={keyword}
              onChange={(event) => {
                setPage(1);
                setKeyword(event.target.value);
              }}
              placeholder="搜索标题 / 品牌 / 品类..."
              className="w-full rounded-lg border border-line bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-primary/50"
            />
          </div>
        </div>

        {/* 提醒规则面板（P2） */}
        {tab === "rules" && (
          <div className="mb-4 rounded-xl2 border border-line bg-white p-4 shadow-card">
            <div className="mb-3 text-sm font-semibold text-ink">降价提醒规则</div>
            <div className="space-y-3">
              {rules.map((rule) => (
                <div
                  key={rule.rule_key}
                  className="flex flex-wrap items-center gap-3 rounded-lg bg-subtle px-3 py-2.5 text-sm"
                >
                  <span className="font-mono text-xs text-ink/60">{rule.rule_key}</span>
                  <span className="min-w-40 flex-1 text-xs text-ink/60">{rule.description}</span>
                  {rule.rule_key === "quiet_hours" ? (
                    <label className="flex items-center gap-1 text-xs">
                      静默时段
                      <input
                        type="time"
                        defaultValue={rule.start ?? "22:00"}
                        onBlur={(e) => saveRule({ ...rule, start: e.target.value })}
                        className="rounded border border-line bg-white px-1.5 py-0.5"
                        aria-label="静默开始时间"
                      />
                      至
                      <input
                        type="time"
                        defaultValue={rule.end ?? "08:00"}
                        onBlur={(e) => saveRule({ ...rule, end: e.target.value })}
                        className="rounded border border-line bg-white px-1.5 py-0.5"
                        aria-label="静默结束时间"
                      />
                    </label>
                  ) : (
                    <>
                      <label className="flex items-center gap-1.5 text-xs">
                        <input
                          type="checkbox"
                          checked={rule.enabled ?? true}
                          onChange={(e) => saveRule({ ...rule, enabled: e.target.checked })}
                        />
                        启用
                      </label>
                      <label className="flex items-center gap-1 text-xs">
                        每日上限
                        <input
                          type="number"
                          min={1}
                          max={20}
                          defaultValue={rule.max_per_day ?? 3}
                          onBlur={(e) => {
                            const value = Math.max(1, Math.min(20, Number(e.target.value) || 3));
                            saveRule({ ...rule, max_per_day: value });
                          }}
                          className="w-14 rounded border border-line bg-white px-1.5 py-0.5"
                        />
                      </label>
                    </>
                  )}
                </div>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-muted">
              规则保存后由价格检查脚本下次运行时读取生效（服务器 crontab 每小时执行）。
            </p>
          </div>
        )}

        {/* 商品表 */}
        <div className="overflow-x-auto rounded-xl2 border border-line bg-white shadow-card">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-subtle text-xs font-semibold text-ink/60">
              <tr>
                <th className="px-3 py-2.5">ID</th>
                <th className="px-3 py-2.5">标题</th>
                <th className="px-3 py-2.5">品类</th>
                <th className="px-3 py-2.5">品牌</th>
                <th className="px-3 py-2.5">到手价</th>
                <th className="px-3 py-2.5">评分</th>
                <th className="px-3 py-2.5">月销</th>
                <th className="px-3 py-2.5">状态</th>
                <th className="px-3 py-2.5">操作</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={9} className="px-3 py-8 text-center text-muted">
                    加载中...
                  </td>
                </tr>
              )}
              {!loading &&
                items.map((product) => (
                  <tr key={product.product_id} className="border-t border-line/60">
                    <td className="px-3 py-2.5 font-mono text-xs text-ink/50">{product.product_id}</td>
                    <td className="max-w-56 truncate px-3 py-2.5 text-ink">{product.title}</td>
                    <td className="px-3 py-2.5 text-ink/70">{product.category_name}</td>
                    <td className="px-3 py-2.5 text-ink/70">{product.brand ?? "-"}</td>
                    <td className="px-3 py-2.5 font-semibold text-price">
                      ¥{product.promotion_price ?? product.price}
                    </td>
                    <td className="px-3 py-2.5">{product.rating}</td>
                    <td className="px-3 py-2.5 text-ink/70">{product.sales_30d ?? "-"}</td>
                    <td className="px-3 py-2.5">
                      <span
                        className={
                          product.status === "on_sale"
                            ? "rounded bg-good/10 px-1.5 py-0.5 text-[11px] text-good"
                            : "rounded bg-subtle px-1.5 py-0.5 text-[11px] text-ink/50"
                        }
                      >
                        {product.status === "on_sale" ? "在售" : "下架"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex gap-1.5">
                        <button
                          type="button"
                          onClick={() => setEditing(product)}
                          className="rounded border border-line px-2 py-1 text-xs text-ink/60 transition hover:border-primary/40 hover:text-primary"
                        >
                          编辑
                        </button>
                        <button
                          type="button"
                          onClick={() => setReviewsFor(product.product_id)}
                          className="rounded border border-line px-2 py-1 text-xs text-ink/60 transition hover:border-primary/40 hover:text-primary"
                        >
                          评价
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDelete(product.product_id)}
                          aria-label={`删除 ${product.title}`}
                          className="rounded border border-line p-1.5 text-muted transition hover:border-risk/40 hover:text-risk"
                        >
                          <Trash2 className="h-3 w-3" aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {/* 分页 */}
        <div className="mt-3 flex items-center justify-between text-xs text-ink/50">
          <span>共 {total} 款商品</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="rounded border border-line px-2.5 py-1 transition hover:border-primary/40 disabled:opacity-40"
            >
              上一页
            </button>
            <span className="self-center">
              {page} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="rounded border border-line px-2.5 py-1 transition hover:border-primary/40 disabled:opacity-40"
            >
              下一页
            </button>
          </div>
        </div>
      </div>

      {editing && (
        <EditDrawer
          product={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            flash("已保存（重建索引后对推荐生效）");
            void load();
          }}
        />
      )}
      {reviewsFor && <ReviewsDrawer productId={reviewsFor} onClose={() => setReviewsFor(null)} />}
    </div>
  );
}

/** 商品编辑抽屉：基本信息 + 风险摘要两个区块 */
function EditDrawer({
  product,
  onClose,
  onSaved,
}: {
  product: AdminProduct;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    title: product.title,
    brand: product.brand ?? "",
    price: String(product.price),
    promotion_price: String(product.promotion_price ?? ""),
    stock: String(product.stock ?? ""),
    status: product.status,
    risk_summary: "",
    suitable_for: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  // N12.17：统一抽屉焦点管理（首焦点/Esc/Tab 循环/关闭回焦）
  const { panelRef, closeRef, handleClose } = useDrawerFocus(true, onClose);

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await patchAdminProduct(product.product_id, {
        title: form.title,
        brand: form.brand || null,
        price: Number(form.price) || undefined,
        promotion_price: form.promotion_price ? Number(form.promotion_price) : null,
        stock: form.stock ? Number(form.stock) : null,
        status: form.status as "on_sale" | "off_sale",
      });
      if (form.risk_summary || form.suitable_for) {
        await patchRiskSummary(product.product_id, {
          risk_summary: form.risk_summary || undefined,
          suitable_for: form.suitable_for || undefined,
        });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 grid justify-end bg-ink/40 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="编辑商品"
      onClick={(event) => event.target === event.currentTarget && handleClose()}
    >
      <div
        ref={panelRef}
        className="drawer-panel h-full w-full max-w-md overflow-y-auto rounded-l-xl3 bg-white p-6 shadow-drawer"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-ink">编辑商品</h2>
          <button
            ref={closeRef}
            type="button"
            onClick={handleClose}
            aria-label="关闭"
            className="grid h-9 w-9 place-items-center rounded-full text-ink/45 transition hover:bg-soft hover:text-ink"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {error && <div className="mb-3 rounded bg-risk/10 px-3 py-2 text-sm text-risk">{error}</div>}

        <div className="space-y-3 text-sm">
          <Field label="标题">
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="input"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="品牌">
              <input value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} className="input" />
            </Field>
            <Field label="状态">
              <select
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
                className="input"
              >
                <option value="on_sale">在售</option>
                <option value="off_sale">下架</option>
              </select>
            </Field>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Field label="原价">
              <input value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} className="input" />
            </Field>
            <Field label="到手价">
              <input
                value={form.promotion_price}
                onChange={(e) => setForm({ ...form, promotion_price: e.target.value })}
                className="input"
              />
            </Field>
            <Field label="库存">
              <input value={form.stock} onChange={(e) => setForm({ ...form, stock: e.target.value })} className="input" />
            </Field>
          </div>
          <Field label="风险摘要（留空不改）">
            <textarea
              value={form.risk_summary}
              onChange={(e) => setForm({ ...form, risk_summary: e.target.value })}
              rows={3}
              className="input resize-none"
            />
          </Field>
          <Field label="适合人群（留空不改）">
            <textarea
              value={form.suitable_for}
              onChange={(e) => setForm({ ...form, suitable_for: e.target.value })}
              rows={2}
              className="input resize-none"
            />
          </Field>
        </div>

        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          className="mt-5 inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-primary-dark disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Save className="h-4 w-4" aria-hidden="true" />}
          {saving ? "保存中..." : "保存"}
        </button>
        <p className="mt-3 text-center text-[11px] text-muted">
          保存只写 MySQL；点顶部"一键重建索引"后对推荐生效
        </p>

        <style>{`.input { width: 100%; border: 1px solid #D7E0DB; border-radius: 0.5rem; padding: 0.5rem 0.75rem; outline: none; } .input:focus { border-color: rgba(31, 93, 75, 0.5); }`}</style>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink/60">{label}</span>
      {children}
    </label>
  );
}

/** 评价样本抽屉（只读） */
function ReviewsDrawer({ productId, onClose }: { productId: string; onClose: () => void }) {
  const [items, setItems] = useState<Array<{ review_id: string; rating: number; content: string; sentiment: string | null }>>([]);
  const [loading, setLoading] = useState(true);
  // N12.17：统一抽屉焦点管理
  const { panelRef, closeRef, handleClose } = useDrawerFocus(true, onClose);

  useEffect(() => {
    fetchProductReviews(productId)
      .then((data) => setItems(data.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [productId]);

  return (
    <div
      className="fixed inset-0 z-50 grid justify-end bg-ink/40 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="评价样本"
      onClick={(event) => event.target === event.currentTarget && handleClose()}
    >
      <div
        ref={panelRef}
        className="drawer-panel h-full w-full max-w-md overflow-y-auto rounded-l-xl3 bg-white p-6 shadow-drawer"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-ink">评价样本（{productId}）</h2>
          <button
            ref={closeRef}
            type="button"
            onClick={handleClose}
            aria-label="关闭"
            className="grid h-9 w-9 place-items-center rounded-full text-ink/45 transition hover:bg-soft hover:text-ink"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        {loading && <p className="text-sm text-muted">正在加载评价样本...</p>}
        {!loading && items.length === 0 && <p className="text-sm text-muted">暂无评价</p>}
        <div className="space-y-3">
          {items.map((review) => (
            <div key={review.review_id} className="rounded-lg border border-line p-3">
              <div className="mb-1 flex items-center gap-2 text-xs">
                <span className="font-semibold text-ink/70">{review.rating} 星</span>
                {review.sentiment && (
                  <span
                    className={
                      review.sentiment === "negative"
                        ? "rounded bg-risk/10 px-1.5 text-risk"
                        : "rounded bg-good/10 px-1.5 text-good"
                    }
                  >
                    {review.sentiment}
                  </span>
                )}
              </div>
              <p className="text-sm leading-5 text-ink/75">{review.content}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
