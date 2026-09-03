"""
SQL 执行节点

负责执行最终 SQL，并记录查询结果。
执行前用 sqlglot 做只读硬校验兜底：理论上前置校验闭环已拦截非查询语句，
这里再次校验是防止任何路径把非 SELECT 语句带到执行环节。
它是当前 SQL 闭环的结束节点，执行完成后流程进入 END。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.sql_guard import validate_readonly
from app.agent.state import DataAgentState
from app.core.log import logger


async def run_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """执行 SQL 并产出最终问数结果"""

    writer = runtime.stream_writer
    step = "执行SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 这里拿到的可能是 generate_sql 直接通过校验的 SQL，也可能是 correct_sql 覆盖后的 SQL
        sql = state["sql"]

        # 只读硬校验兜底：非单条 SELECT 一律拒绝执行，以 error 事件终止
        guard_error = validate_readonly(sql)
        if guard_error is not None:
            logger.error(f"执行前只读校验未通过：{guard_error}")
            writer({"type": "progress", "step": step, "status": "error"})
            writer({"type": "error", "message": f"拒绝执行非只读 SQL：{guard_error}"})
            return {}

        dw_mysql_repository = runtime.context["dw_mysql_repository"]

        # 真实数据库访问统一封装在仓储层，节点只负责从状态取 SQL 并触发执行
        result = await dw_mysql_repository.run(sql)
        logger.info(f"SQL执行结果：{result}")
        rows = result if isinstance(result, list) else [result]
        empty = len(rows) == 0

        # 首次空结果且尚未自检过：不发 result 事件，转交 self_check 分析重试；
        # 自检后的第二轮无论是否为空都正常收尾
        if empty and not state.get("empty_retry_done"):
            writer({"type": "progress", "step": step, "status": "success"})
            return {"result_data": rows, "result_empty": True}

        writer({"type": "progress", "step": step, "status": "success"})
        writer({"type": "result", "data": rows})
        return {"result_data": rows, "result_empty": empty}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
