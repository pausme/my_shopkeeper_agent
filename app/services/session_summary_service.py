"""
会话总结服务（二期 S1-3）

从会话消息与推荐结果生成"总结卡"：一段可读总结、未决问题、关注商品。
无 LLM 依赖的规则版：从落库消息直接提取（推荐摘要即主结论，
追问即未决问题），保证摘要可重建、不漂移。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import ProductInfoMySQL
from app.models.shopping import (
    ShoppingMessageMySQL,
    ShoppingRecommendationMySQL,
    ShoppingSessionSummaryMySQL,
)
from app.repositories.mysql.meta.shopping_repositories import new_id


class SessionSummaryService:
    """会话总结的生成与读取"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _resolve_focus_names(self, product_ids: list[str]) -> list[str]:
        """N11.29：关注商品对外只显示名称，不暴露 P0005 这类内部编号

        名称缺失（商品被软删）时退化为"已关注商品N"占位。
        """

        if not product_ids:
            return []
        result = await self.session.execute(
            select(ProductInfoMySQL.product_id, ProductInfoMySQL.title).where(
                ProductInfoMySQL.product_id.in_(product_ids),
                ProductInfoMySQL.is_deleted == 0,
            )
        )
        titles = {row.product_id: row.title for row in result}
        return [
            titles.get(pid, f"已关注商品{index + 1}")
            for index, pid in enumerate(product_ids)
        ]

    async def generate(self, session_id: str, user_id: str | None) -> dict | None:
        """生成（或刷新）会话总结；会话不存在返回 None"""

        # 读会话消息
        msg_result = await self.session.execute(
            select(ShoppingMessageMySQL)
            .where(
                ShoppingMessageMySQL.session_id == session_id,
                ShoppingMessageMySQL.is_deleted == 0,
            )
            .order_by(ShoppingMessageMySQL.created_at)
        )
        messages = list(msg_result.scalars())
        if not messages:
            return None

        # 主结论 = 最后一条推荐摘要；未决问题 = 所有追问问题
        recommendations: list[str] = []
        unresolved: list[str] = []
        focus_ids: list[str] = []
        for message in messages:
            if message.message_type == "clarification":
                unresolved.append(message.content)
            elif message.message_type == "recommendation":
                recommendations.append(message.content)

        # 关注商品 = 最后一次推荐的 product_id（取 result_json）
        rec_result = await self.session.execute(
            select(ShoppingRecommendationMySQL)
            .where(ShoppingRecommendationMySQL.session_id == session_id)
            .order_by(ShoppingRecommendationMySQL.id.desc())
            .limit(1)
        )
        last_rec = rec_result.scalars().first()
        if last_rec and last_rec.result_json:
            for item in last_rec.result_json.get("recommendations") or []:
                pid = item.get("product_id")
                if pid and pid not in focus_ids:
                    focus_ids.append(pid)

        if not recommendations and not unresolved:
            return None

        summary_text = (
            recommendations[-1]
            if recommendations
            else "本轮咨询尚未产生推荐结论，还有问题待确认。"
        )

        # 覆盖式保存（可重建：删旧插新）
        old_result = await self.session.execute(
            select(ShoppingSessionSummaryMySQL).where(
                ShoppingSessionSummaryMySQL.session_id == session_id
            )
        )
        for old in old_result.scalars():
            await self.session.delete(old)

        summary_row = ShoppingSessionSummaryMySQL(
            summary_id=new_id("SM"),
            session_id=session_id,
            user_id=user_id,
            summary_text=summary_text[:2000],
            unresolved_questions_json=unresolved[:5],
            focus_products_json=focus_ids[:5],
        )
        self.session.add(summary_row)
        await self.session.commit()

        return {
            "summary_id": summary_row.summary_id,
            "session_id": session_id,
            "summary_text": summary_text,
            "unresolved_questions": unresolved[:5],
            "focus_products": await self._resolve_focus_names(focus_ids[:5]),
        }

    async def get(self, session_id: str) -> dict | None:
        """读取已有总结；无则返回 None"""

        result = await self.session.execute(
            select(ShoppingSessionSummaryMySQL)
            .where(ShoppingSessionSummaryMySQL.session_id == session_id)
            .order_by(ShoppingSessionSummaryMySQL.id.desc())
            .limit(1)
        )
        row = result.scalars().first()
        if row is None:
            return None
        return {
            "summary_id": row.summary_id,
            "session_id": row.session_id,
            "summary_text": row.summary_text,
            "unresolved_questions": row.unresolved_questions_json or [],
            "focus_products": await self._resolve_focus_names(row.focus_products_json or []),
        }
