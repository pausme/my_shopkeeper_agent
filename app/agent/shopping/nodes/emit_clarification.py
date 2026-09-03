"""
追问输出节点（导购链路）

发出 clarification SSE 事件并把本轮问答落库，随后流程结束等待用户补充
"""

from langgraph.runtime import Runtime

from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.core.log import logger


async def emit_clarification(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """输出追问事件并持久化消息"""

    writer = runtime.stream_writer
    question = state.get("clarification_question") or "可以再描述一下您的需求吗？"
    session_id = state["session_id"]

    try:
        repository = runtime.context["shopping_session_repository"]
        if repository is not None:
            await repository.ensure_session(
                session_id, state.get("user_id"), state["query"]
            )
            await repository.save_message(
                session_id, "user", state["query"], "query"
            )
            await repository.save_message(
                session_id, "assistant", question, "clarification"
            )
            await repository.session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"追问消息落库失败（不影响输出）：{e}")

    writer(
        {
            "type": "clarification",
            "question": question,
            "options": state.get("clarification_options") or [],
            "session_id": session_id,
            "clarification_count": state.get("clarification_count", 0) + 1,
        }
    )
    return {}
