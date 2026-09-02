"""
指标召回节点

负责根据检索词从指标向量知识库中召回候选指标
它帮助 Agent 把“销售额 转化率 客单价”等业务表达映射到已定义指标
检索词来自 jieba 关键词和 extend_keywords 节点的指标层扩展词
本节点把逐词串行检索改为并发执行，缩短召回环节耗时
"""

import asyncio

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.entities.metric_info import MetricInfo


async def recall_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """召回和用户问题语义相关的业务指标"""

    writer = runtime.stream_writer
    step = "召回指标信息"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # query 兜底与指标层扩展词来自 extend_keywords 节点，keywords 来自 jieba 抽取
        keywords = state["keywords"]
        extended = state.get("extended_keywords", {}).get("metric_keywords", [])
        # 指标召回使用向量检索，需要 Embedding 客户端和指标 Qdrant 仓储配合
        embedding_client = runtime.context["embedding_client"]
        metric_qdrant_repository = runtime.context["metric_qdrant_repository"]

        # 通用关键词和指标扩展词都参与召回，提升同义指标的命中率
        keyword_list = list(set(list(keywords) + list(extended)))

        # 先并发向量化，再并发向量检索
        embeddings = await asyncio.gather(
            *(embedding_client.aembed_query(keyword) for keyword in keyword_list)
        )
        search_results = await asyncio.gather(
            *(metric_qdrant_repository.search(embedding) for embedding in embeddings)
        )

        # 用指标 id 做唯一键，避免多个关键词命中同一个指标时重复写入 state
        metric_info_map: dict[str, MetricInfo] = {}
        for current_metric_infos in search_results:
            for metric_info in current_metric_infos:
                if metric_info.id not in metric_info_map:
                    metric_info_map[metric_info.id] = metric_info

        # 写回 state 的是业务实体列表，后续过滤节点不需要关心 Qdrant 原始 point 结构
        retrieved_metric_infos: list[MetricInfo] = list(metric_info_map.values())
        logger.info(f"检索到指标信息：{list(metric_info_map.keys())}")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"retrieved_metric_infos": retrieved_metric_infos}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
