"""
导购智能体运行时上下文

复用 meta MySQL（商品/风险摘要）、Qdrant（商品语义召回）、ES（评价检索）
与 Embedding 客户端；会话落库仓储由节点按需从 context 读取
"""

from typing import TYPE_CHECKING, TypedDict

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.es.review_es_repository import ReviewESRepository
from app.repositories.mysql.meta.product_repository import ProductRepository
from app.repositories.qdrant.product_qdrant_repository import ProductQdrantRepository

if TYPE_CHECKING:
    from app.repositories.mysql.meta.shopping_repositories import (
        ShoppingSessionRepository,
    )


class ShoppingAgentContext(TypedDict):
    """导购图执行上下文：节点通过 runtime.context 读取"""

    product_repository: ProductRepository
    product_qdrant_repository: ProductQdrantRepository
    review_es_repository: ReviewESRepository
    embedding_client: object
    # meta 库会话，供 persist 节点写会话/消息/推荐结果
    meta_session: AsyncSession
    shopping_session_repository: "ShoppingSessionRepository | None"
    qdrant_client: AsyncQdrantClient | None
