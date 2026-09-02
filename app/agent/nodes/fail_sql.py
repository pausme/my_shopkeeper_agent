"""
SQL 终止节点

当 SQL 校验失败且修正次数达到上限时进入该节点
它不执行任何 SQL，而是把带上下文的错误信息以 error 事件流式返回给前端，随后流程进入 END
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# SQL 校验失败后允许的最大修正次数，超过后不再重试直接终止
MAX_SQL_RETRIES = 3


async def fail_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """修正重试耗尽后终止流程，并向前端返回可解释的错误信息"""

    writer = runtime.stream_writer
    error = state.get("error") or "未知错误"
    retry_count = state.get("sql_retry_count", 0)

    message = (
        f"SQL 校验未通过，已尝试修正 {retry_count} 次仍失败，本次查询已终止。"
        f"最后一次错误：{error}"
    )
    logger.error(message)
    writer({"type": "error", "message": message})
    return {}
