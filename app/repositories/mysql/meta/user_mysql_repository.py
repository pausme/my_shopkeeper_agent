"""
用户与认证仓储

负责 user 表的数据访问：按用户名查重/查询、注册落库。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserMySQL


class UserMySQLRepository:
    """负责用户数据的持久化与查询"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_username(self, username: str) -> UserMySQL | None:
        """按登录名查询用户"""

        result = await self.session.execute(
            select(UserMySQL).where(UserMySQL.username == username)
        )
        return result.scalar_one_or_none()

    async def create(self, username: str, password_hash: str) -> UserMySQL:
        """创建新用户并落库（不提交，事务由上层会话管理）"""

        user = UserMySQL(username=username, password_hash=password_hash)
        self.session.add(user)
        await self.session.flush()
        return user
