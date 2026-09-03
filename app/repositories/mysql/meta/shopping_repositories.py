"""
导购会话仓储

shopping_session / shopping_message / shopping_recommendation / shopping_feedback
四张表的读写，供导购链路落库与会话查询接口使用
"""

import json
import uuid

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shopping import (
    ShoppingEventLogMySQL,
    ShoppingFeedbackMySQL,
    ShoppingMessageMySQL,
    ShoppingRecommendationMySQL,
    ShoppingSessionMySQL,
)


def new_id(prefix: str) -> str:
    """业务 ID：前缀 + 去连字符 UUID，满足唯一性与可读性"""

    return f"{prefix}{uuid.uuid4().hex[:20].upper()}"


class ShoppingSessionRepository:
    """导购会话域的持久化"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- 会话 ----------

    async def ensure_session(
        self, session_id: str, user_id: str | None, title: str | None
    ) -> ShoppingSessionMySQL:
        """会话不存在则创建；存在则刷新最近输入与标题"""

        result = await self.session.execute(
            select(ShoppingSessionMySQL).where(ShoppingSessionMySQL.session_id == session_id)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            row = ShoppingSessionMySQL(
                session_id=session_id,
                user_id=user_id,
                title=(title or "新导购会话")[:255],
                status="active",
                last_query=(title or "")[:1024],
            )
            self.session.add(row)
            return row
        existing.last_query = (title or existing.last_query or "")[:1024]
        return existing

    async def list_sessions(self, user_id: str | None, limit: int = 50) -> list[dict]:
        """按最近更新列出会话"""

        conditions = [ShoppingSessionMySQL.is_deleted == 0]
        if user_id:
            conditions.append(ShoppingSessionMySQL.user_id == user_id)
        result = await self.session.execute(
            select(ShoppingSessionMySQL)
            .where(*conditions)
            .order_by(desc(ShoppingSessionMySQL.updated_at))
            .limit(limit)
        )
        return [
            {
                "session_id": row.session_id,
                "title": row.title,
                "scene_tag": row.scene_tag,
                "status": row.status,
                "last_query": row.last_query,
                "updated_at": int(row.updated_at.timestamp() * 1000) if row.updated_at else None,
            }
            for row in result.scalars()
        ]

    async def get_session_messages(self, session_id: str) -> list[dict]:
        """按时间列出会话消息"""

        result = await self.session.execute(
            select(ShoppingMessageMySQL)
            .where(
                ShoppingMessageMySQL.session_id == session_id,
                ShoppingMessageMySQL.is_deleted == 0,
            )
            .order_by(ShoppingMessageMySQL.created_at)
        )
        return [
            {
                "message_id": row.message_id,
                "role": row.role,
                "content": row.content,
                "message_type": row.message_type,
                "trace": row.trace_json,
                "created_at": int(row.created_at.timestamp() * 1000) if row.created_at else None,
            }
            for row in result.scalars()
        ]

    async def delete_session(self, session_id: str) -> bool:
        """逻辑删除会话及其消息（M9.3 隐私控制：用户可清除自己的导购历史）"""

        result = await self.session.execute(
            select(ShoppingSessionMySQL).where(ShoppingSessionMySQL.session_id == session_id)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            return False
        existing.is_deleted = 1
        await self.session.execute(
            update(ShoppingMessageMySQL)
            .where(ShoppingMessageMySQL.session_id == session_id)
            .values(is_deleted=1)
        )
        return True

    # ---------- 消息与推荐结果 ----------

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        message_type: str,
        message_id: str | None = None,
        trace: dict | None = None,
    ) -> str:
        """写一条消息，返回消息 ID"""

        message_id = message_id or new_id("M")
        self.session.add(
            ShoppingMessageMySQL(
                message_id=message_id,
                session_id=session_id,
                role=role,
                content=content,
                message_type=message_type,
                trace_json=trace,
            )
        )
        return message_id

    async def save_recommendation(
        self,
        session_id: str,
        message_id: str,
        query_text: str,
        result_json: dict,
        comparison_json: dict | None,
    ) -> str:
        recommendation_id = new_id("RC")
        self.session.add(
            ShoppingRecommendationMySQL(
                recommendation_id=recommendation_id,
                session_id=session_id,
                message_id=message_id,
                query_text=query_text[:1024],
                result_json=json.loads(json.dumps(result_json, ensure_ascii=False, default=str)),
                comparison_json=comparison_json,
            )
        )
        return recommendation_id

    # ---------- 反馈 ----------

    async def save_event(
        self,
        session_id: str,
        message_id: str | None,
        user_id: str | None,
        event_type: str,
        event_data: dict | None = None,
    ) -> None:
        """写入导购埋点事件（append-only，失败不影响主链路）"""

        self.session.add(
            ShoppingEventLogMySQL(
                session_id=session_id,
                message_id=message_id,
                user_id=user_id,
                event_type=event_type,
                event_data_json=event_data or {},
            )
        )

    async def save_feedback(
        self,
        session_id: str,
        message_id: str | None,
        feedback_type: str,
        product_id: str | None = None,
        user_id: str | None = None,
        comment: str | None = None,
    ) -> str:
        feedback_id = new_id("FB")
        self.session.add(
            ShoppingFeedbackMySQL(
                feedback_id=feedback_id,
                session_id=session_id,
                message_id=message_id,
                product_id=product_id,
                user_id=user_id,
                feedback_type=feedback_type,
                comment=(comment or "")[:1024],
            )
        )
        return feedback_id
