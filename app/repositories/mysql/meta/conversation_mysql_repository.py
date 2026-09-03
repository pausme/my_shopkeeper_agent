"""
会话仓储

负责 conversation / message 表的数据访问：按用户列出会话壳、读写整块消息 JSON。
"""

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import ConversationMySQL, MessageMySQL


class ConversationMySQLRepository:
    """负责问数会话的持久化"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_user(self, user_id: int) -> list[dict]:
        """按用户列出会话（含消息），按最近更新倒序"""

        result = await self.session.execute(
            select(ConversationMySQL)
            .where(ConversationMySQL.user_id == user_id)
            .order_by(ConversationMySQL.updated_at.desc())
        )
        conversations = result.scalars().all()

        if not conversations:
            return []

        # 一次取出所有消息，按会话分组，避免逐会话 N+1 查询
        ids = [conversation.id for conversation in conversations]
        messages_result = await self.session.execute(
            select(MessageMySQL).where(MessageMySQL.conversation_id.in_(ids))
        )
        messages_by_conversation: dict[str, list] = {}
        for row in messages_result.scalars():
            messages_by_conversation.setdefault(row.conversation_id, []).append(
                json.loads(row.messages)
            )

        return [
            {
                "id": conversation.id,
                "title": conversation.title,
                "createdAt": int(conversation.created_at.timestamp() * 1000)
                if conversation.created_at
                else None,
                "updatedAt": int(conversation.updated_at.timestamp() * 1000)
                if conversation.updated_at
                else None,
                "messages": messages_by_conversation.get(conversation.id, [])[0]
                if messages_by_conversation.get(conversation.id)
                else [],
            }
            for conversation in conversations
        ]

    async def upsert(
        self, user_id: int, conversation_id: str, title: str, messages: list[dict]
    ) -> None:
        """创建或整体覆盖一个会话（消息整块替换，幂等且语义简单）"""

        existing = await self.session.get(ConversationMySQL, conversation_id)
        if existing is None:
            self.session.add(
                ConversationMySQL(id=conversation_id, user_id=user_id, title=title)
            )
        else:
            # 会话只能被属主修改（调用方保证 user_id 校验），标题跟随首问更新
            existing.title = title

        messages_json = json.dumps(messages, ensure_ascii=False)
        result = await self.session.execute(
            select(MessageMySQL).where(MessageMySQL.conversation_id == conversation_id)
        )
        message_row = result.scalar_one_or_none()
        if message_row is None:
            self.session.add(
                MessageMySQL(conversation_id=conversation_id, messages=messages_json)
            )
        else:
            message_row.messages = messages_json

    async def delete(self, user_id: int, conversation_id: str) -> bool:
        """删除属主会话及其消息；返回是否确实删除了会话"""

        result = await self.session.execute(
            delete(ConversationMySQL).where(
                ConversationMySQL.id == conversation_id,
                ConversationMySQL.user_id == user_id,
            )
        )
        return (result.rowcount or 0) > 0
