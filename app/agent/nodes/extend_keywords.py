"""
检索词扩展节点

把三路召回各自的关键词扩展合并为一次 LLM 调用：
统一产出 column_keywords / metric_keywords / value_keywords 三组检索词写入状态，
recall_column / recall_metric / recall_value 节点直接消费，避免三节点各自调用 LLM
"""

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, format_history
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt

# LLM 输出缺失某组检索词时的兜底结构
EMPTY_EXTENDED_KEYWORDS: dict[str, list[str]] = {
    "column_keywords": [],
    "metric_keywords": [],
    "value_keywords": [],
}


async def extend_keywords(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """用一次 LLM 调用为三路召回统一扩展检索词"""

    writer = runtime.stream_writer
    step = "扩展检索词"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 优先消费改写后的独立问题；history 保留为辅助上下文
        query = state.get("rewritten_query") or state["query"]
        history_text = format_history(state.get("history")) or "无"

        prompt = PromptTemplate(
            template=load_prompt("extend_recall_keywords"),
            input_variables=["query", "history"],
        )
        # 组合 prompt 要求只输出包含三组检索词的 JSON 对象
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"query": query, "history": history_text})

        # LLM 偶发漏字段时补齐，下游节点按空列表处理即可
        if not isinstance(result, dict):
            result = dict(EMPTY_EXTENDED_KEYWORDS)
        for key, default in EMPTY_EXTENDED_KEYWORDS.items():
            if not isinstance(result.get(key), list):
                result[key] = default

        logger.info(f"扩展检索词：{result}")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"extended_keywords": result}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
