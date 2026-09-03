"""
意图与槽位抽取节点（导购链路）

一次 LLM 调用同时完成意图识别（recommendation/comparison/summary/followup）
与购买槽位抽取（品类/场景/预算/人群/偏好/排除项），结果写入状态供后续节点使用。
附耗时观测日志（PRD 13.4）
"""

import time

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.llm import llm
from app.agent.shopping.category_match import guess_category
from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState, format_history
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt

# 槽位默认结构：LLM 漏字段时以此兜底
EMPTY_SLOTS: dict = {
    "category": None,
    "scene": None,
    "budget_min": None,
    "budget_max": None,
    "audience": None,
    "preferences": [],
    "exclusions": [],
    "product_ids": [],
}


async def extract_intent_slots(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """识别导购意图并抽取购买槽位"""

    writer = runtime.stream_writer
    step = "理解需求"
    writer({"type": "progress", "step": step, "status": "running"})
    started = time.monotonic()

    try:
        query = state.get("rewritten_query") or state["query"]
        history_text = format_history(state.get("history")) or "无"
        selected_ids = state.get("selected_product_ids") or []
        last_ids = state.get("last_recommended_ids") or []

        prompt = PromptTemplate(
            template=load_prompt("extract_intent_slots"),
            input_variables=["query", "history", "selected_product_ids", "last_product_ids"],
        )
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = await chain.ainvoke(
            {
                "query": query,
                "history": history_text,
                "selected_product_ids": ", ".join(selected_ids) or "无",
                "last_product_ids": ", ".join(last_ids) or "无",
            }
        )
        if not isinstance(result, dict):
            result = {"intent": "recommendation"}
        for key, default in EMPTY_SLOTS.items():
            if result.get(key) is None:
                result[key] = default
        intent = result.get("intent") or "recommendation"

        # 品类安全网：LLM 漏抽时用关键词映射兜底（品类硬过滤依赖它，不能为空）
        if not result["category"]:
            fallback = guess_category(query, state.get("rewritten_query"))
            if fallback:
                result["category"] = fallback
                logger.info(f"LLM 品类缺失，关键词兜底补全：{fallback}")

        logger.info(
            f"导购意图：{intent}，槽位：{result}，耗时 {time.monotonic() - started:.2f}s"
        )
        writer({"type": "progress", "step": step, "status": "success"})
        return {"intent": intent, "purchase_slots": result}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
