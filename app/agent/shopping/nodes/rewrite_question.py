"""
追问改写节点（导购链路复用）

多轮对话里用户经常用省略式追问（"那华东呢""2 月呢"），直接拿去检索和生成
效果很差。本节点用 LLM 结合最近对话把追问改写成独立完整的问题写入状态；
没有历史对话时跳过 LLM 直接透传，后续节点统一消费 rewritten_query
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.agent.llm import llm
from app.agent.shopping.state import ShoppingAgentState, format_history
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def rewrite_question(state: ShoppingAgentState, runtime):
    """把省略式追问改写为独立问题；独立问题与无历史场景直接透传"""

    query = state["query"]
    history_text = format_history(state.get("history"))

    # 没有历史对话时无需改写，直接透传原问题
    if not history_text:
        return {"rewritten_query": query}

    step = "改写追问"
    runtime.stream_writer({"type": "progress", "step": step, "status": "running"})

    try:
        prompt = PromptTemplate(
            template=load_prompt("rewrite_question"),
            input_variables=["query", "history"],
        )
        # 改写只需要纯文本问题输出
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

        result = (await chain.ainvoke({"query": query, "history": history_text})).strip()

        # 模型偶发输出空串或复读原文，都视为改写失败，回退原问题保证链路可用
        rewritten = result if result else query
        logger.info(f"追问改写：{query} -> {rewritten}")
        runtime.stream_writer({"type": "progress", "step": step, "status": "success"})
        return {"rewritten_query": rewritten}
    except Exception as e:
        logger.error(f"{step} failed: {e}，回退原问题")
        runtime.stream_writer({"type": "progress", "step": step, "status": "error"})
        return {"rewritten_query": query}
