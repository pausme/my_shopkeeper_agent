"""
追问决策节点（导购链路）

规则判断（不调 LLM）：信息不足时决定是否追问。受 PRD 约束最多追问有限轮次，
且已有历史对话（多轮后半程）不再追问，避免用户流失
"""

from langgraph.runtime import Runtime

from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.core.log import logger

# 单次会话最多追问次数（PRD：最多连续追问 2 次，这里保守取 1）
MAX_CLARIFICATION = 1

CATEGORY_QUESTION = "想先确认一下：您想看哪个品类的商品？目前支持厨房小电器、家居生活、数码配件、母婴用品。"
BUDGET_QUESTION = "您的预算大概是多少？告诉我上限后，我能把推荐收敛得更准。"


async def decide_clarification(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """判断是否需要向用户追问关键缺失信息"""

    writer = runtime.stream_writer
    step = "判断是否追问"
    writer({"type": "progress", "step": step, "status": "running"})

    slots = state.get("purchase_slots") or {}
    intent = state.get("intent", "recommendation")
    has_history = bool(state.get("history"))
    asked = state.get("clarification_count", 0)

    question = None
    if (
        intent == "recommendation"
        and not has_history
        and asked < MAX_CLARIFICATION
        and not slots.get("product_ids")
    ):
        if not slots.get("category"):
            question = CATEGORY_QUESTION
        elif not slots.get("budget_max") and not slots.get("budget_min"):
            question = BUDGET_QUESTION

    logger.info(f"追问决策：{'需要' if question else '不需要'}追问")
    writer({"type": "progress", "step": step, "status": "success"})
    return {
        "clarification_needed": question is not None,
        "clarification_question": question or "",
    }
