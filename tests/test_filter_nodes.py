"""
filter_table / filter_metric 过滤节点单元测试

节点内部的 LLM 调用链用 RunnableLambda 替身替换（monkeypatch 模块级 llm 符号），
只验证"模型返回选择结果后，程序按选择裁剪原始结构"的核心逻辑。
"""

import asyncio
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda


def run(coro):
    return asyncio.run(coro)


def make_runtime():
    # 节点只用到 stream_writer 和 context，测试里给最小替身
    return SimpleNamespace(stream_writer=lambda event: None, context={})


def make_column(name: str) -> dict:
    return {
        "name": name,
        "type": "varchar(50)",
        "role": "dimension",
        "examples": [],
        "description": f"{name} 描述",
        "alias": [],
    }


def test_filter_table_trims_columns_and_tables(monkeypatch):
    from app.agent.nodes import filter_table as module

    # 替身输出 JSON 字符串，与真实 LLM 的输出形态一致，交给 JsonOutputParser 解析
    monkeypatch.setattr(
        module, "llm", RunnableLambda(lambda _: '{"dim_region": ["region_name"]}')
    )

    state = {
        "query": "华北地区",
        "table_infos": [
            {
                "name": "dim_region",
                "role": "dim",
                "description": "地区维度",
                "columns": [make_column("region_name"), make_column("province")],
            },
            {
                "name": "dim_customer",
                "role": "dim",
                "description": "客户维度",
                "columns": [make_column("customer_name")],
            },
        ],
    }

    result = run(module.filter_table(state, make_runtime()))

    assert [table["name"] for table in result["table_infos"]] == ["dim_region"]
    assert [column["name"] for column in result["table_infos"][0]["columns"]] == [
        "region_name"
    ]


def test_filter_table_drops_unselected_table(monkeypatch):
    from app.agent.nodes import filter_table as module

    monkeypatch.setattr(module, "llm", RunnableLambda(lambda _: "{}"))

    state = {
        "query": "随便问问",
        "table_infos": [
            {
                "name": "dim_region",
                "role": "dim",
                "description": "",
                "columns": [make_column("region_name")],
            }
        ],
    }

    result = run(module.filter_table(state, make_runtime()))
    assert result["table_infos"] == []


def test_filter_metric_keeps_selected(monkeypatch):
    from app.agent.nodes import filter_metric as module

    monkeypatch.setattr(module, "llm", RunnableLambda(lambda _: '["GMV"]'))

    state = {
        "query": "销售总额",
        "metric_infos": [
            {
                "name": "GMV",
                "description": "成交金额总和",
                "relevant_columns": ["fact_order.order_amount"],
                "alias": ["成交总额"],
            },
            {
                "name": "AOV",
                "description": "平均订单金额",
                "relevant_columns": ["fact_order.order_amount"],
                "alias": ["平均单价"],
            },
        ],
    }

    result = run(module.filter_metric(state, make_runtime()))

    assert [metric["name"] for metric in result["metric_infos"]] == ["GMV"]
    assert result["metric_infos"][0]["relevant_columns"] == ["fact_order.order_amount"]
