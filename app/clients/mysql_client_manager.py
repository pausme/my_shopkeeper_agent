"""
MySQL 客户端管理器

统一创建和管理项目中的异步 MySQL 客户端，连接保存商品与导购业务数据的
meta 数据库。模块对外提供可复用的客户端管理器和 session 工厂，
方便脚本入口 服务层和仓储层按统一方式访问数据库
"""

import asyncio

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.conf.app_config import DBConfig, app_config


class MySQLClientManager:
    """管理 MySQL Engine 和 Session 工厂"""

    def __init__(self, config: DBConfig):
        # Engine 是数据库连接层核心对象，底层会维护连接池
        self.engine: AsyncEngine | None = None
        # session_factory 用来按需创建新的 AsyncSession
        self.session_factory = None
        # 保存数据库配置，后面拼接连接地址要用
        self.config = config

    def _get_url(self) -> str:
        """
        拼接 MySQL 异步连接地址
        mysql+asyncmy 表示：连接 MySQL，并使用 asyncmy 作为异步驱动
        """
        return f"mysql+asyncmy://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}?charset=utf8mb4"

    def init(self):
        """初始化 Engine 和 Session 工厂"""
        # 创建异步 Engine，相当于先把“数据库连接能力”准备好
        self.engine = create_async_engine(
            self._get_url(), pool_size=10, pool_pre_ping=True
        )
        # 基于 Engine 创建 Session 工厂，后面真正查库时再拿 session
        self.session_factory = async_sessionmaker(
            self.engine, autoflush=True, expire_on_commit=False
        )

    async def close(self):
        """释放连接池资源"""
        await self.engine.dispose()


# 商品与导购业务数据的唯一数据库入口
meta_mysql_client_manager = MySQLClientManager(app_config.db_meta)

if __name__ == "__main__":
    meta_mysql_client_manager.init()

    async def test():
        """执行一次简单查询，验证 MySQL 连接与结果结构"""
        async with meta_mysql_client_manager.session_factory() as session:
            from sqlalchemy import func, select

            from app.models.product import ProductInfoMySQL

            result = await session.execute(select(func.count()).select_from(ProductInfoMySQL))
            print("商品数:", result.scalar())

    asyncio.run(test())
