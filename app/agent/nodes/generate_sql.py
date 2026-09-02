"""
SQL 组合生成节点

把"过滤候选表字段/指标"与"生成 SQL"合并为一次 LLM 调用：
模型在同一个提示词里先完成候选筛选、再产出最终 SQL（JSON 输出），
减少一次串行 LLM 调用，缩短端到端延迟。
本节点只产出候选 SQL，校验与执行由 validate_sql / run_sql 负责。
"""

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from yaml import dump as yaml_dump

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, format_history
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def generate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """一次性完成候选过滤与 SQL 生成"""

    writer = runtime.stream_writer
    step = "生成SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 合并节点产出的候选上下文（未过滤），筛选在本节点的提示词内完成
        table_infos = state["table_infos"]
        metric_infos = state["metric_infos"]
        date_info = state["date_info"]
        db_info = state["db_info"]
        # 生成消费改写后的独立问题（无历史时等于原问题），避免省略式追问直接进提示词
        query = state.get("rewritten_query") or state["query"]
        history_text = format_history(state.get("history")) or "无"

        prompt = PromptTemplate(
            template=load_prompt("compose_sql"),
            input_variables=[
                "table_infos",
                "metric_infos",
                "date_info",
                "db_info",
                "query",
                "history",
            ],
        )
        # compose_sql 要求输出 {selected_tables, selected_metrics, sql} 的 JSON 对象
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = await chain.ainvoke(
            {
                # YAML 更适合放进提示词：保留嵌套结构 顺序和中文说明，方便模型理解表字段关系
                "table_infos": yaml_dump(
                    table_infos, allow_unicode=True, sort_keys=False
                ),
                "metric_infos": yaml_dump(
                    metric_infos, allow_unicode=True, sort_keys=False
                ),
                "date_info": yaml_dump(date_info, allow_unicode=True, sort_keys=False),
                "db_info": yaml_dump(db_info, allow_unicode=True, sort_keys=False),
                "query": query,
                "history": history_text,
            }
        )

        if not isinstance(result, dict):
            raise ValueError(f"compose_sql 输出不是 JSON 对象：{str(result)[:120]}")
        sql = str(result.get("sql", "")).strip()
        if not sql:
            raise ValueError("compose_sql 输出中缺少 sql 字段")

        # 筛选结果仅用于观测，不影响后续节点（修正节点仍使用完整上下文）
        logger.info(
            f"compose_sql 筛选：tables={result.get('selected_tables')} "
            f"metrics={result.get('selected_metrics')}"
        )
        logger.info(f"生成的SQL：{sql}")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"sql": sql}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
