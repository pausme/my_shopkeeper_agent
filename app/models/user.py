"""
用户表 ORM 模型

问数系统的注册用户：登录名唯一，密码存 PBKDF2 哈希（stdlib 实现，无额外依赖）
"""

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserMySQL(Base):
    """用户表对应的 ORM 模型"""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="登录名"
    )
    # PBKDF2-SHA256 哈希，格式 "iterations:salt_hex:hash_hex"
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False, comment="密码哈希")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), comment="注册时间"
    )
