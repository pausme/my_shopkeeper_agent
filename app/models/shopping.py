"""
导购会话业务表 ORM 模型（AI 商品决策助手）

shopping_session 会话 / shopping_message 消息 / shopping_recommendation 推荐结果
shopping_feedback 用户反馈 / shopping_event_log 查询埋点
"""

from sqlalchemy import JSON, BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ShoppingSessionMySQL(Base):
    """导购会话表"""

    __tablename__ = "shopping_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True, comment="用户 ID")
    scene_tag: Mapped[str | None] = mapped_column(String(64), comment="场景标签")
    title: Mapped[str | None] = mapped_column(String(255), comment="会话标题")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", comment="active/stopped/completed"
    )
    last_query: Mapped[str | None] = mapped_column(String(1024), comment="最近一次用户输入")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
    is_deleted: Mapped[int] = mapped_column(default=0, comment="逻辑删除")

    __table_args__ = (Index("idx_user_updated_at", "user_id", "updated_at"),)


class ShoppingMessageMySQL(Base):
    """导购消息表"""

    __tablename__ = "shopping_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, comment="user/assistant/system")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    message_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="query/clarification/recommendation/comparison/error",
    )
    trace_json: Mapped[dict | None] = mapped_column(JSON, comment="执行过程")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    is_deleted: Mapped[int] = mapped_column(default=0, comment="逻辑删除")

    __table_args__ = (Index("idx_session_created_at", "session_id", "created_at"),)


class ShoppingRecommendationMySQL(Base):
    """推荐结果表"""

    __tablename__ = "shopping_recommendation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    query_text: Mapped[str] = mapped_column(String(1024), nullable=False, comment="用户问题")
    result_json: Mapped[dict | None] = mapped_column(JSON, comment="推荐结果整体结构")
    comparison_json: Mapped[dict | None] = mapped_column(JSON, comment="对比信息")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    is_deleted: Mapped[int] = mapped_column(default=0, comment="逻辑删除")


class ShoppingFeedbackMySQL(Base):
    """用户反馈表"""

    __tablename__ = "shopping_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    feedback_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(String(64), comment="消息 ID")
    product_id: Mapped[str | None] = mapped_column(String(64), comment="关联商品")
    user_id: Mapped[str | None] = mapped_column(String(64), comment="用户 ID")
    feedback_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="helpful/unhelpful/not_accurate/too_expensive/too_few/not_understand",
    )
    comment: Mapped[str | None] = mapped_column(String(1024), comment="补充说明")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    is_deleted: Mapped[int] = mapped_column(default=0, comment="逻辑删除")


class ShoppingEventLogMySQL(Base):
    """查询埋点表（append-only）"""

    __tablename__ = "shopping_event_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(String(64), comment="消息 ID")
    user_id: Mapped[str | None] = mapped_column(String(64), comment="用户 ID")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="事件类型")
    event_data_json: Mapped[dict | None] = mapped_column(JSON, comment="事件内容")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
