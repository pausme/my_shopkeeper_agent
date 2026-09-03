"""
评价全文检索仓储

把商品评价组织成 Elasticsearch 全文索引，支撑差评关键词与评价内容召回
value 字段沿用 IK 中文分词，与字段取值索引保持一致的检索体验
"""

from dataclasses import asdict

from elasticsearch import AsyncElasticsearch


class ReviewESRepository:
    """负责商品评价全文索引的创建、写入和检索"""

    index_name = "review_index"
    index_mappings = {
        "dynamic": False,
        "properties": {
            "review_id": {"type": "keyword"},
            "product_id": {"type": "keyword"},
            "rating": {"type": "integer"},
            "content": {
                "type": "text",
                "analyzer": "ik_max_word",
                "search_analyzer": "ik_max_word",
            },
            "sentiment": {"type": "keyword"},
            "review_tags": {"type": "keyword"},
        },
    }

    def __init__(self, client: AsyncElasticsearch):
        self.client = client

    async def ensure_index(self):
        if not await self.client.indices.exists(index=self.index_name):
            await self.client.indices.create(
                index=self.index_name, mappings=self.index_mappings
            )

    async def drop_index(self):
        """删除索引，供种子脚本全量重建使用"""

        if await self.client.indices.exists(index=self.index_name):
            await self.client.indices.delete(index=self.index_name)

    async def index_reviews(self, reviews: list[dict], batch_size: int = 100):
        """批量写入评价文档，重复构建按 review_id 覆盖"""

        if not reviews:
            return
        for i in range(0, len(reviews), batch_size):
            batch = reviews[i : i + batch_size]
            operations = []
            for review in batch:
                operations.append(
                    {"index": {"_index": self.index_name, "_id": review["review_id"]}}
                )
                operations.append(asdict(_ReviewDoc(**review)))
            await self.client.bulk(operations=operations)

    async def search_negative(
        self, product_id: str, keyword: str, limit: int = 10
    ) -> list[dict]:
        """检索某商品差评中包含关键词的评价，用于风险佐证"""

        resp = await self.client.search(
            index=self.index_name,
            query={
                "bool": {
                    "filter": [
                        {"term": {"product_id": product_id}},
                        {"term": {"sentiment": "negative"}},
                    ],
                    "must": [{"match": {"content": keyword}}],
                }
            },
            size=limit,
        )
        return [hit["_source"] for hit in resp["hits"]["hits"]]

    async def count_by_sentiment(self, product_id: str) -> dict[str, int]:
        """按情感聚合某商品的评价数，用于样本量与差评占比计算"""

        resp = await self.client.search(
            index=self.index_name,
            query={"term": {"product_id": product_id}},
            aggs={"by_sentiment": {"terms": {"field": "sentiment"}}},
            size=0,
        )
        return {
            bucket["key"]: bucket["doc_count"]
            for bucket in resp["aggregations"]["by_sentiment"]["buckets"]
        }


class _ReviewDoc:
    """ES 文档结构（评价的精简投影）"""

    def __init__(
        self,
        review_id: str,
        product_id: str,
        rating: int,
        content: str,
        sentiment: str | None = None,
        review_tags: list[str] | None = None,
    ):
        self.review_id = review_id
        self.product_id = product_id
        self.rating = rating
        self.content = content
        self.sentiment = sentiment
        self.review_tags = review_tags or []
