"""
商品向量仓储

管理商品语义向量集合，支持按需求文本召回候选商品
embedding_text 由种子脚本组装（标题+类目+品牌+核心属性），payload 存商品主数据
"""

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.conf.app_config import app_config


class ProductQdrantRepository:
    """负责商品向量集合的创建、写入和语义检索"""

    collection_name = "product_info_collection"

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def ensure_collection(self):
        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=app_config.qdrant.embedding_size, distance=Distance.COSINE
                ),
            )

    async def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        payloads: list[dict],
        batch_size: int = 10,
    ):
        from qdrant_client.http.models import PointStruct

        points = [
            PointStruct(id=id, vector=embedding, payload=payload)
            for id, embedding, payload in zip(ids, embeddings, payloads)
        ]
        for i in range(0, len(points), batch_size):
            await self.client.upsert(
                collection_name=self.collection_name, points=points[i : i + batch_size]
            )

    async def search(
        self, embedding: list[float], score_threshold: float = 0.3, limit: int = 12
    ) -> list[dict]:
        """语义召回候选商品，返回 payload（含 product_id 与相似度分数）"""

        result = await self.client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            limit=limit,
            score_threshold=score_threshold,
        )
        payloads = []
        for point in result.points:
            payload = dict(point.payload)
            payload["semantic_score"] = point.score
            payloads.append(payload)
        return payloads

    async def drop_collection(self):
        """删除集合，供种子脚本全量重建使用"""

        if await self.client.collection_exists(self.collection_name):
            await self.client.delete_collection(self.collection_name)
