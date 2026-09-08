"""
提醒规则配置模型（二期 P2）

rule_key 唯一（如 global / quiet_hours），
value_json 存该规则的参数（限频/静默期/开关）。
"""

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AlertRuleMySQL(Base):
    """提醒规则配置表（运营可编辑）"""

    __tablename__ = "shopping_alert_rule"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rule_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="规则键")
    description: Mapped[str | None] = mapped_column(String(255), comment="规则说明")
    # enabled: 是否启用；quiet_hours: 静默时段；max_per_day: 单用户每日上限
    value_json: Mapped[dict | None] = mapped_column(JSON, comment="规则参数")
    updated_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
