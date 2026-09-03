"""
导购问答服务

组装导购图的运行时上下文（商品主库/向量召回/评价检索/会话仓储），
消费 shopping_graph.astream 的自定义事件流并包装为 SSE 输出。
附带两个进程内缓存（均模块级，跨请求共享）：
- 查询缓存：相同单轮问题 10 分钟内直接回放事件（PRD 13.1 缓存命中 ≤3s）
- 会话上轮推荐缓存：供"帮我比较前两个"类追问选取商品（PRD 10.8）
"""

import json
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.graph import shopping_graph
from app.agent.shopping.state import ShoppingAgentState
from app.repositories.es.review_es_repository import ReviewESRepository
from app.repositories.mysql.meta.product_repository import ProductRepository
from app.repositories.mysql.meta.shopping_repositories import ShoppingSessionRepository
from app.repositories.qdrant.product_qdrant_repository import ProductQdrantRepository

CACHE_TTL_SECONDS = 600
CACHE_MAX_ENTRIES = 100

# 查询缓存：query 文本 -> (过期时间, SSE 事件列表)。仅缓存无历史的单轮查询
_query_cache: dict[str, tuple[float, list[dict]]] = {}

# 会话上轮推荐：session_id -> (过期时间, 按推荐顺序的 product_ids)
_session_last_products: dict[str, tuple[float, list[str]]] = {}


def _cache_get(query: str) -> list[dict] | None:
    now = time.monotonic()
    for key in [k for k, (deadline, _) in _query_cache.items() if deadline <= now]:
        _query_cache.pop(key, None)
    entry = _query_cache.get(query)
    return entry[1] if entry else None


def _cache_put(query: str, events: list[dict]):
    _query_cache[query] = (time.monotonic() + CACHE_TTL_SECONDS, events)
    while len(_query_cache) > CACHE_MAX_ENTRIES:
        _query_cache.pop(next(iter(_query_cache)))


def _last_products_get(session_id: str) -> list[str]:
    entry = _session_last_products.get(session_id)
    if entry is None:
        return []
    deadline, ids = entry
    if deadline <= time.monotonic():
        _session_last_products.pop(session_id, None)
        return []
    return ids


def _last_products_put(session_id: str, product_ids: list[str]):
    _session_last_products[session_id] = (
        time.monotonic() + CACHE_TTL_SECONDS,
        product_ids,
    )
    while len(_session_last_products) > CACHE_MAX_ENTRIES:
        _session_last_products.pop(next(iter(_session_last_products)))


class ShoppingAgentService:
    """导购链路的业务编排"""

    def __init__(
        self,
        session: AsyncSession,
        product_repository: ProductRepository,
        product_qdrant_repository: ProductQdrantRepository,
        review_es_repository: ReviewESRepository,
        embedding_client,
    ):
        # 请求级 meta 会话贯穿整次导购执行，落库与查询共用
        self.session = session
        self.product_repository = product_repository
        self.product_qdrant_repository = product_qdrant_repository
        self.review_es_repository = review_es_repository
        self.embedding_client = embedding_client
        self.shopping_session_repository = ShoppingSessionRepository(session)

    async def query(
        self,
        query: str,
        session_id: str | None = None,
        history: list[dict] | None = None,
        selected_product_ids: list[str] | None = None,
        scene_tag: str | None = None,
        user_id: str | None = None,
        clarification_count: int = 0,
    ):
        """执行一次导购工作流，逐段产出 SSE 消息"""

        session_id = session_id or f"S{uuid.uuid4().hex[:20].upper()}"

        def sse(event: dict) -> str:
            return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

        # 会话开始即告知前端 session_id，后续轮次与反馈都依赖它
        yield sse({"type": "progress", "step": "开始导购", "status": "running", "session_id": session_id})

        # 缓存命中：无历史的单轮相同问题直接回放事件（PRD 13.1 缓存命中 ≤3s）
        history = history or []
        if not history and not selected_product_ids:
            cached = _cache_get(query)
            if cached is not None:
                for event in cached:
                    event["session_id"] = session_id
                    event["cached"] = True
                    yield sse(event)
                return

        last_ids = _last_products_get(session_id) if session_id else []
        state = ShoppingAgentState(
            query=query,
            rewritten_query=query,
            history=history,
            session_id=session_id,
            user_id=user_id,
            intent="recommendation",
            purchase_slots={},
            selected_product_ids=selected_product_ids or [],
            clarification_needed=False,
            clarification_question="",
            clarification_options=[],
            clarification_count=clarification_count,
            last_recommended_ids=last_ids,
            candidate_products=[],
            review_summary={},
            risk_summary={},
            ranked_products=[],
            recommendation={},
            comparison_table={},
            error=None,
        )
        context = ShoppingAgentContext(
            product_repository=self.product_repository,
            product_qdrant_repository=self.product_qdrant_repository,
            review_es_repository=self.review_es_repository,
            embedding_client=self.embedding_client,
            meta_session=self.session,
            shopping_session_repository=self.shopping_session_repository,
            qdrant_client=None,
        )
        events: list[dict] = []
        try:
            async for chunk in shopping_graph.astream(
                input=state, context=context, stream_mode="custom"
            ):
                if scene_tag and chunk.get("type") == "recommendation":
                    chunk["scene_tag"] = scene_tag
                events.append(chunk)
                yield sse(chunk)
        except Exception as e:
            yield sse({"type": "error", "message": f"导购服务异常：{e}"})
            return

        # 更新两个缓存：完整推荐结果入查询缓存；推荐商品顺序入会话上轮推荐
        if events and events[-1].get("type") == "comparison":
            if not history:
                _cache_put(query, events)
            recommended_event = next(
                (e for e in reversed(events) if e.get("type") == "recommendation"), None
            )
            if recommended_event:
                ids = [p["product_id"] for p in recommended_event.get("recommended_products", [])]
                if ids:
                    _last_products_put(session_id, ids)

    # ---------- 非流式辅助查询 ----------

    async def product_summary(self, product_id: str) -> dict | None:
        """商品简介 + 评价摘要 + 风险提示"""

        rows = await self.product_repository.get_by_product_ids([product_id])
        if not rows:
            return None
        row = rows[0]
        risk = await self.product_repository.get_risk_summary(product_id)
        return {
            "product_id": row.product_id,
            "title": row.title,
            "category_name": row.category_name,
            "brand": row.brand,
            "price": float(row.price),
            "promotion_price": float(row.promotion_price) if row.promotion_price else None,
            "rating": float(row.rating),
            "sales_30d": row.sales_30d,
            "review_count": row.review_count,
            "attributes": row.attributes_json or {},
            "risk": {
                "level": risk.risk_level if risk else "unknown",
                "summary": risk.risk_summary if risk else "",
                "positive_summary": risk.positive_summary if risk else "",
                "suitable_for": risk.suitable_for if risk else "",
                "not_suitable_for": risk.not_suitable_for if risk else "",
                "sample_size": risk.sample_size if risk else 0,
            },
        }

    async def compare_products(self, product_ids: list[str]) -> dict | None:
        """指定商品的结构化对比（不走 LLM）"""

        rows = await self.product_repository.get_by_product_ids(product_ids)
        if len(rows) < 2:
            return None
        categories = {row.category_name for row in rows}
        cross_category = len(categories) > 1
        rows_with_risk = []
        for row in rows:
            risk = await self.product_repository.get_risk_summary(row.product_id)
            rows_with_risk.append(
                {
                    "product_id": row.product_id,
                    "商品": row.title,
                    "到手价": f"{float(row.promotion_price or row.price)} 元",
                    "评分": f"{float(row.rating)}（月销 {row.sales_30d}）",
                    "关键属性": "；".join(
                        f"{k}:{v}" for k, v in list((row.attributes_json or {}).items())[:4]
                    ),
                    "风险提示": risk.risk_summary if risk else "",
                    "适合人群": risk.suitable_for if risk else "",
                    "不适合": risk.not_suitable_for if risk else "",
                }
            )
        headers = list(rows_with_risk[0].keys())
        return {
            "headers": headers,
            "rows": rows_with_risk,
            "cross_category_warning": (
                "所选商品属于不同品类，参数不具备直接可比性，仅供参考。" if cross_category else ""
            ),
        }
