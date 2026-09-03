"""
Rerank 客户端管理器

管理 bge-reranker TEI 服务的访问：把粗排候选按与查询的相关度精排。
服务不可用或超时时返回 None，调用方回退到原始排序——精排是增强，不是依赖。
"""

import asyncio
from typing import Optional

import httpx

from app.conf.app_config import app_config
from app.core.log import logger


class RerankClientManager:
    """封装 TEI /rerank 端点的异步调用"""

    def __init__(self, config):
        self.config = config
        # 客户端进程级复用；超时远小于 LLM 调用，精排卡死时快速降级
        self._client: Optional[httpx.AsyncClient] = None

    def init(self):
        self._client = httpx.AsyncClient(
            base_url=f"http://{self.config.host}:{self.config.port}", timeout=10
        )

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self.init()
        return self._client

    async def rerank(self, query: str, texts: list[str], top_k: int = 5) -> Optional[list[int]]:
        """返回按相关度排序的前 top_k 个候选下标；服务异常返回 None"""

        if not texts:
            return []
        try:
            response = await self.client.post(
                "/rerank", json={"query": query, "texts": texts, "raw_scores": False}
            )
            response.raise_for_status()
            results = response.json()
            # TEI 返回 [{index, score}, ...]，已按分数降序
            return [item["index"] for item in results[:top_k]]
        except Exception as e:  # noqa: BLE001
            logger.warning(f"rerank 服务不可用，回退原始排序：{e}")
            return None

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# 模块级单例，供依赖注入与本地调试复用
rerank_client_manager = RerankClientManager(app_config.rerank)


if __name__ == "__main__":
    rerank_client_manager.init()

    async def test():
        """最小化验证 rerank 服务可用性"""
        order = await rerank_client_manager.rerank(
            "地区销售额", ["region_name 地区名称", "gender 客户性别", "order_amount 订单金额"], top_k=2
        )
        print(order)

    asyncio.run(test())
