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

    # 品型候选不足提示合并进 summary（findings #24/#26）
    note = (state.get("insufficient_note") or "").strip()
    if note:
        summary = recommendation.get("summary", "")
        if note not in summary:
            recommendation = {**recommendation, "summary": f"{note}{summary}"}

    # findings #25：展示集由 generate 节点统一计算（卡与表同源），此处直接消费
    recommended = list(state.get("display_products") or [])

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
    # 回归 8.3-2：仅主动对比（显式选品或对比意图）才发送对比表；
    # 普通推荐轮不自动展开完整对比，避免覆盖推荐主结论
    is_active_compare = bool(
        state.get("selected_product_ids")
        or (state.get("intent") == "comparison")
    )
    if is_active_compare and comparison:
        writer({"type": "comparison", "session_id": session_id, "table": comparison})
    return {}
