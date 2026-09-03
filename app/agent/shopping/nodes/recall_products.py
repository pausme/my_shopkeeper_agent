"""
商品召回节点（导购链路）

三级策略（PRD 10.3）：
1. 用户显式指定商品 ID 时直查主库；
2. 否则语义召回（改写需求+槽位拼接文本）+ 主库补全校正（在售+有库存）；
3. 召回不足 5 款时按品类热销补召回；向量服务异常时降级为品类热销（PRD 13.2）
"""

import time

from langgraph.runtime import Runtime

from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.conf.app_config import app_config
from app.core.log import logger

# 召回候选不足该数量时触发热销补召回
TOP_UP_THRESHOLD = 5


async def recall_products(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """召回候选商品并补全主数据"""

    writer = runtime.stream_writer
    step = "召回商品"
    writer({"type": "progress", "step": step, "status": "running"})
    started = time.monotonic()

    try:
        product_repository = runtime.context["product_repository"]
        product_qdrant = runtime.context["product_qdrant_repository"]
        embedding_client = runtime.context["embedding_client"]

        slots = state.get("purchase_slots") or {}
        selected_ids = state.get("selected_product_ids") or slots.get("product_ids") or []
        category = slots.get("category")
        recall_limit = app_config.shopping.recall_limit
        recall_threshold = app_config.shopping.recall_threshold

        if selected_ids:
            rows = await product_repository.get_by_product_ids(selected_ids)
            candidates = [_row_to_candidate(row, 1.0) for row in rows]
        else:
            # 拼接语义检索文本：改写需求 + 槽位要素，强化品类/场景/偏好的向量表达
            parts = [state.get("rewritten_query") or state["query"]]
            for key in ("category", "scene", "audience"):
                if slots.get(key):
                    parts.append(str(slots[key]))
            parts.extend(slots.get("preferences") or [])
            search_text = " ".join(parts)

            # 语义召回；向量服务异常时降级为品类热销（PRD 13.2）
            try:
                embedding = await embedding_client.aembed_query(search_text)
                payloads = await product_qdrant.search(
                    embedding, score_threshold=recall_threshold, limit=recall_limit
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"语义召回失败，降级为品类热销：{exc}")
                payloads = []

            ids = [payload["product_id"] for payload in payloads]
            rows = {row.product_id: row for row in await product_repository.get_by_product_ids(ids)}
            candidates = []
            for payload in payloads:
                row = rows.get(payload["product_id"])
                if row is not None:
                    candidates.append(_row_to_candidate(row, payload.get("semantic_score", 0.0)))

            # 热销补召回：语义候选不足时，按品类（无品类则全局）近 30 天销量补充
            if len(candidates) < TOP_UP_THRESHOLD:
                exclude = {c["product_id"] for c in candidates}
                hot = await product_repository.list_by_category(
                    category_name=category, limit=recall_limit
                )
                for row in hot:
                    if row.product_id not in exclude:
                        candidates.append(_row_to_candidate(row, 0.0))
                        exclude.add(row.product_id)
                logger.info(f"热销补召回：候选补至 {len(candidates)} 款")

        logger.info(
            f"召回候选商品 {len(candidates)} 款，耗时 {time.monotonic() - started:.2f}s"
        )
        writer({"type": "progress", "step": step, "status": "success"})
        return {"candidate_products": candidates}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise


def _row_to_candidate(row, semantic_score: float) -> dict:
    """ORM 行 -> 候选商品字典（后续节点与 SSE 全程使用 JSON 友好结构）"""

    return {
        "product_id": row.product_id,
        "title": row.title,
        "category_name": row.category_name,
        "brand": row.brand,
        "price": float(row.price),
        "promotion_price": float(row.promotion_price) if row.promotion_price else None,
        "stock": row.stock,
        "sales_30d": row.sales_30d,
        "rating": float(row.rating),
        "review_count": row.review_count,
        "attributes": row.attributes_json or {},
        "semantic_score": round(float(semantic_score), 4),
    }
