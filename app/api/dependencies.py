"""
FastAPI 依赖组装

集中声明导购接口需要的依赖：请求级 Meta 会话、导购服务与会话仓储。
HTTP 处理函数只通过 Depends 声明需要什么，创建细节收敛在这里。
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.review_es_repository import ReviewESRepository
from app.repositories.mysql.meta.product_repository import ProductRepository
from app.repositories.mysql.meta.shopping_repositories import (
    ShoppingSessionRepository,
)
from app.repositories.qdrant.product_qdrant_repository import (
    ProductQdrantRepository,
)
from app.services.shopping_agent_service import ShoppingAgentService


async def get_meta_session():
    """创建一次请求内使用的元数据库 Session"""

    async with meta_mysql_client_manager.session_factory() as session:
        yield session


async def get_shopping_service(
    session: Annotated[AsyncSession, Depends(get_meta_session)],
) -> ShoppingAgentService:
    """组装导购服务：请求级 meta 会话 + 商品域仓储 + 向量/评价检索"""

    return ShoppingAgentService(
        session=session,
        product_repository=ProductRepository(session),
        product_qdrant_repository=ProductQdrantRepository(qdrant_client_manager.client),
        review_es_repository=ReviewESRepository(es_client_manager.client),
        embedding_client=embedding_client_manager.client,
    )


async def get_shopping_session_repository():
    """导购会话仓储（供列表/详情/反馈等轻接口使用）"""

    async with meta_mysql_client_manager.session_factory() as session:
        yield ShoppingSessionRepository(session)
