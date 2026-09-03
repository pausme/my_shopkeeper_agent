"""
字段召回节点

负责根据检索词从字段向量知识库中召回候选字段
它解决的是“用户问题可能对应哪些数据库字段”的问题
检索词来自 jieba 关键词和 extend_keywords 节点的字段层扩展词
本节点把逐词串行检索改为并发执行，缩短召回环节耗时
"""

import asyncio

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.entities.column_info import ColumnInfo


async def recall_column(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """召回和用户问题语义相关的字段元数据"""

    writer = runtime.stream_writer
    step = "召回字段信息"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # state 保存图内业务中间结果：jieba 关键词和 LLM 统一扩展出的字段层检索词
        keywords = state["keywords"]
        extended = state.get("extended_keywords", {}).get("column_keywords", [])
        # context 保存外部运行时工具：向量仓储和 Embedding 客户端
        column_qdrant_repository = runtime.context["column_qdrant_repository"]
        embedding_client = runtime.context["embedding_client"]

        # 原始关键词和扩展词一起参与召回；先转列表，保证并发任务的顺序稳定
        keyword_list = list(set(list(keywords) + list(extended)))

        # 先并发向量化，再并发向量检索，避免逐词串行等待
        embeddings = await asyncio.gather(
            *(embedding_client.aembed_query(keyword) for keyword in keyword_list)
        )
        search_results = await asyncio.gather(
            *(column_qdrant_repository.search(embedding) for embedding in embeddings)
        )

        # 用字段 id 做唯一键，因为多个关键词、同一字段的多个向量点都可能命中同一个字段
        column_info_map: dict[str, ColumnInfo] = {}
        for current_column_infos in search_results:
            for column_info in current_column_infos:
                if column_info.id not in column_info_map:
                    column_info_map[column_info.id] = column_info

        candidates: list[ColumnInfo] = list(column_info_map.values())

        # 粗排候选较多时用 reranker 精排：以改写后的完整问题为查询，保留最相关前 5 个字段。
        # 精排是增强而非依赖——服务不可用时保持原始排序继续走
        rerank_manager = runtime.context.get("rerank_client")
        top_k = 5
        if rerank_manager is not None and len(candidates) > top_k:
            rerank_query = state.get("rewritten_query") or state["query"]
            texts = [
                f"{column_info.name}：{column_info.description}" for column_info in candidates
            ]
            indices = await rerank_manager.rerank(rerank_query, texts, top_k=top_k)
            if indices is not None:
                logger.info(
                    f"字段精排：{len(candidates)} -> {[candidates[i].id for i in indices]}"
                )
                candidates = [candidates[i] for i in indices]

        # 写回 state 的是去重与精排后的 ColumnInfo 列表，不暴露 Qdrant 原始 point 结构
        writer({"type": "progress", "step": step, "status": "success"})
        return {"retrieved_column_infos": candidates}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
