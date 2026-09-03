"""
问数查询服务

负责把 API 层传入的自然语言问题转换成一次 LangGraph 工作流执行：
创建初始 State、组装 Runtime Context、消费 graph.astream 的流式输出，
并统一包装成 SSE 文本返回给路由层。
附带一个进程内的短 TTL 查询缓存：完全相同的问题在窗口期内直接回放历史事件。
"""

import json
import time

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

# 相同问题的缓存有效期（秒）与最大缓存条数，避免长期占用内存
CACHE_TTL_SECONDS = 600
CACHE_MAX_ENTRIES = 50

# 模块级缓存：每个请求都会通过依赖注入新建 QueryService 实例，
# 缓存必须放在模块级才能跨请求复用
_query_cache: dict[str, tuple[float, list[dict]]] = {}


class QueryService:
    """封装一次问数查询所需的业务编排逻辑"""

    def __init__(
        self,
        meta_mysql_repository: MetaMySQLRepository,
        embedding_client: HuggingFaceEndpointEmbeddings,
        dw_mysql_repository: DWMySQLRepository,
        column_qdrant_repository: ColumnQdrantRepository,
        metric_qdrant_repository: MetricQdrantRepository,
        value_es_repository: ValueESRepository,
        rerank_client=None,
    ):
        # MySQL 仓储分别负责元数据补全和真实数仓环境信息读取
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository

        # 召回链路依赖的向量检索、Embedding 和全文检索能力由依赖层注入
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository
        # rerank 精排客户端；未注入时召回节点自动回退原始排序
        self.rerank_client = rerank_client

        # 进程内查询缓存：query 文本 -> (过期时间戳, SSE 事件对象列表)

    def _cache_get(self, query: str) -> list[dict] | None:
        """命中未过期的缓存时返回历史事件，并顺手清理过期条目"""

        now = time.monotonic()
        expired = [
            key for key, (deadline, _) in _query_cache.items() if deadline <= now
        ]
        for key in expired:
            _query_cache.pop(key, None)

        entry = _query_cache.get(query)
        if entry is None:
            return None
        return entry[1]

    def _cache_put(self, query: str, events: list[dict]):
        """仅缓存成功拿到结果的查询；超量时按插入顺序淘汰最早的条目"""

        _query_cache[query] = (time.monotonic() + CACHE_TTL_SECONDS, events)
        while len(_query_cache) > CACHE_MAX_ENTRIES:
            _query_cache.pop(next(iter(_query_cache)))

    async def query(self, query: str, history: list[dict] | None = None):
        """执行一次问数工作流，并逐段产出 SSE 消息"""

        def sse(event: dict) -> str:
            # SSE 要求每条消息以 data: 开头，并以两个换行符结束
            # ensure_ascii=False 保留中文进度文案，default=str 兜底处理日期等非 JSON 类型
            return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

        # 命中缓存时直接回放历史事件，跳过整条工作流
        cached_events = self._cache_get(query)
        if cached_events is not None:
            for event in cached_events:
                yield sse(event)
            return

        # State 只放会被图节点读写和合并的业务数据，外部工具对象不塞进 State
        state = DataAgentState(query=query, history=history or [])
        # Context 保存本次图执行需要复用的外部依赖，节点通过 runtime.context 读取
        context = DataAgentContext(
            column_qdrant_repository=self.column_qdrant_repository,
            embedding_client=self.embedding_client,
            metric_qdrant_repository=self.metric_qdrant_repository,
            value_es_repository=self.value_es_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository,
            rerank_client=self.rerank_client,
        )
        events: list[dict] = []
        try:
            # stream_mode="custom" 对应节点内部 writer(...) 写出的进度消息
            async for chunk in graph.astream(
                input=state, context=context, stream_mode="custom"
            ):
                events.append(chunk)
                yield sse(chunk)
        except Exception as e:
            # 流式接口已经开始返回后不能再改 HTTP 状态码，因此把异常也包装成一条 SSE 消息
            error = {"type": "error", "message": str(e)}
            yield sse(error)
            return

        # 只缓存完整拿到结果的查询（最后一条事件是 result 才算成功）
        if events and events[-1].get("type") == "result":
            self._cache_put(query, events)
