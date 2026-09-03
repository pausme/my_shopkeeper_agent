"""
导购问答服务

组装导购图的运行时上下文（商品主库/向量召回/评价检索/会话仓储），
消费 shopping_graph.astream 的自定义事件流并包装为 SSE 输出
"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.graph import shopping_graph
from app.agent.shopping.state import ShoppingAgentState
from app.repositories.es.review_es_repository import ReviewESRepository
from app.repositories.mysql.meta.product_repository import ProductRepository
from app.repositories.mysql.meta.shopping_repositories import ShoppingSessionRepository
from app.repositories.qdrant.product_qdrant_repository import ProductQdrantRepository


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

        state = ShoppingAgentState(
            query=query,
            rewritten_query=query,
            history=history or [],
            session_id=session_id,
            user_id=user_id,
            intent="recommendation",
            purchase_slots={},
            selected_product_ids=selected_product_ids or [],
            clarification_needed=False,
            clarification_question="",
            clarification_count=clarification_count,
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
        try:
            async for chunk in shopping_graph.astream(
                input=state, context=context, stream_mode="custom"
            ):
                if scene_tag and chunk.get("type") == "recommendation":
                    chunk["scene_tag"] = scene_tag
                yield sse(chunk)
        except Exception as e:
            yield sse({"type": "error", "message": f"导购服务异常：{e}"})

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
