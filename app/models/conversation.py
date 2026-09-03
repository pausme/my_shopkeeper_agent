"""
会话与消息 ORM 模型

服务端持久化多轮问数会话：conversation 是会话壳，message 存每条聊天消息，
messages 以 JSON 数组整块存储（含步骤/结果/错误信息），读写都以会话为单位，无需按消息建表
"""

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ConversationMySQL(Base):
    """问数会话表对应的 ORM 模型"""

    __tablename__ = "conversation"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="会话ID（前端生成的 UUID）"
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属用户"
    )
    title: Mapped[str] = mapped_column(String(128), default="新会话", comment="会话标题")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="最近更新时间"
    )


class MessageMySQL(Base):
    """会话消息表对应的 ORM 模型"""

    __tablename__ = "message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话",
    )
    # messages 为 ChatMessage 对象数组的 JSON 序列化，单会话整块存取
    messages: Mapped[str] = mapped_column(Text, nullable=False, comment="消息列表 JSON")
