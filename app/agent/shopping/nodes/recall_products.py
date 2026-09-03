"""
商品召回节点（导购链路）

优先使用用户显式指定的商品 ID；否则以改写需求 + 槽位拼接文本做语义召回，
并用商品主库补全/校正在售状态、价格、库存等权威字段
"""


from langgraph.runtime import Runtime

from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.core.log import logger


async def recall_products(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """召回候选商品并补全主数据"""

    writer = runtime.stream_writer
    step = "召回商品"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        product_repository = runtime.context["product_repository"]
        product_qdrant = runtime.context["product_qdrant_repository"]
        embedding_client = runtime.context["embedding_client"]

        slots = state.get("purchase_slots") or {}
        selected_ids = state.get("selected_product_ids") or slots.get("product_ids") or []

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

            embedding = await embedding_client.aembed_query(search_text)
            payloads = await product_qdrant.search(embedding, limit=12)
            ids = [payload["product_id"] for payload in payloads]
            rows = {row.product_id: row for row in await product_repository.get_by_product_ids(ids)}
            candidates = []
            for payload in payloads:
                row = rows.get(payload["product_id"])
                if row is not None:
                    candidates.append(_row_to_candidate(row, payload.get("semantic_score", 0.0)))

        logger.info(f"召回候选商品 {len(candidates)} 款")
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
