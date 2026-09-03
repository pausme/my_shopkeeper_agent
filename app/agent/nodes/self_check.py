"""
空结果自检节点

SQL 执行返回 0 行时进入本节点：结合三路召回拿到的字段真实取值生成一份
"自检提示"，指出可能的空结果原因（条件值与真实存储不一致 / 条件过严），
然后带着提示回到生成节点重试一轮。重试仍为空则由 run_sql 正常返回空结果。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.entities.value_info import ValueInfo


async def self_check(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """分析空结果原因并生成重试提示，随后重新走一次 SQL 生成"""

    writer = runtime.stream_writer
    step = "空结果自检"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 召回阶段拿到的字段真实取值是最有价值的线索：
        # 它们来自 ES 全文索引，代表数仓中真实存储的枚举值
        value_infos: list[ValueInfo] = state.get("retrieved_value_infos") or []
        samples = [
            f"{value_info.column_id}={value_info.value}" for value_info in value_infos[:20]
        ]

        hint_lines = [
            "上一次生成的 SQL 执行结果为 0 行。请自查以下可能原因并重新生成 SQL：",
            "1. WHERE 条件值与数仓真实存储不一致（如 '北京' vs '北京市'），应参考下方真实取值样例；",
            "2. 时间或维度条件过严导致无匹配数据，可适当放宽；",
            "3. 若问题本身在当前数据范围内确实无数据，生成语义等价的查询即可，不要编造数据。",
        ]
        if samples:
            hint_lines.append("字段真实取值样例：" + "；".join(samples))
        else:
            hint_lines.append("本次检索未拿到字段真实取值样例，请重点检查条件值的拼写与粒度。")
        hint = "\n".join(hint_lines)

        logger.info(f"空结果自检：候选取值 {len(value_infos)} 条，生成重试提示")
        writer({"type": "progress", "step": step, "status": "success"})
        # empty_retry_done 保证自检重试至多一轮
        return {"empty_retry_done": True, "self_check_hint": hint}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        # 自检失败不阻断：直接放行为空结果
        return {"empty_retry_done": True, "self_check_hint": ""}
