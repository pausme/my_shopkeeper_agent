"""
会话落库与结果输出节点（导购链路）

把本轮问答（用户输入 + 推荐结果 + 推荐记录 + 埋点事件）写入导购会话表，
并通过 stream_writer 发出 recommendation / comparison 两个 SSE 事件
"""

from langgraph.runtime import Runtime

from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.core.log import logger


async def persist_and_emit(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """落库会话与推荐结果，并输出最终 SSE 事件"""

    writer = runtime.stream_writer
    session_id = state["session_id"]
    recommendation = state.get("recommendation") or {}
    comparison = state.get("comparison_table") or {}
    assistant_message_id = ""

    # 推荐结果：只输出 LLM 给出理由的商品（无理由=模型判定不符合需求，不应硬推）
    ranked = state.get("ranked_products") or []
    reasons = {
        item.get("product_id"): item.get("reason", "")
        for item in recommendation.get("recommendations", [])
    }
    recommended = [
        {**product, "reason": reasons[product["product_id"]]}
        for product in ranked
        if reasons.get(product["product_id"], "").strip()
    ]
    # 兜底：LLM 给出理由的商品不足 3 款时（PRD 15.1：完整需求至少 3 个推荐），
    # 用总结摘录补足头部商品，避免点名商品反被截掉
    if len(recommended) < 3:
        included = {p["product_id"] for p in recommended}
        summary_text = recommendation.get("summary", "")[:80] or "综合评分与销量较高，供参考。"
        for product in ranked:
            if len(recommended) >= 3:
                break
            if product["product_id"] not in included:
                recommended.append({**product, "reason": summary_text})
                included.add(product["product_id"])

    try:
        repository = runtime.context["shopping_session_repository"]
        if repository is not None:
            await repository.ensure_session(session_id, state.get("user_id"), state["query"])
            await repository.save_message(session_id, "user", state["query"], "query")

            summary_text = recommendation.get("summary", "")
            assistant_message_id = await repository.save_message(
                session_id,
                "assistant",
                summary_text,
                "recommendation",
                trace={"steps": ["recall", "analyze", "rank", "generate"]},
            )
            await repository.save_recommendation(
                session_id,
                assistant_message_id,
                state["query"],
                recommendation,
                comparison,
            )
            # 埋点最小闭环（M8.3）：查询发起与推荐曝光
            await repository.save_event(
                session_id, assistant_message_id, state.get("user_id"),
                "query_start", {"query": state["query"]},
            )
            await repository.save_event(
                session_id, assistant_message_id, state.get("user_id"),
                "recommendation_shown", {"count": len(recommended)},
            )
            await repository.session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"会话落库失败（不影响推荐输出）：{e}")

    writer(
        {
            "type": "recommendation",
            "session_id": session_id,
            # message_id 供前端反馈接口追溯（PRD：反馈必须可追溯到 session+message）
            "message_id": assistant_message_id,
            "summary": recommendation.get("summary", ""),
            "next_question": recommendation.get("next_question", ""),
            "recommended_products": recommended,
        }
    )
    writer({"type": "comparison", "session_id": session_id, "table": comparison})
    return {}
