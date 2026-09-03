"""
self_check 空结果自检节点单元测试

只测提示构建与状态标记，不访问外部服务。
"""

import asyncio
from types import SimpleNamespace

from app.entities.value_info import ValueInfo


def run(coro):
    return asyncio.run(coro)


def make_runtime():
    return SimpleNamespace(stream_writer=lambda event: None, context={})


def test_self_check_builds_hint_with_values():
    from app.agent.nodes import self_check as module

    state = {
        "retrieved_value_infos": [
            ValueInfo(id="dim_region.region_name.华北", value="华北", column_id="dim_region.region_name"),
            ValueInfo(id="dim_product.brand.耐克", value="耐克", column_id="dim_product.brand"),
        ]
    }

    result = run(module.self_check(state, make_runtime()))

    assert result["empty_retry_done"] is True
    hint = result["self_check_hint"]
    assert "0 行" in hint and "dim_region.region_name=华北" in hint
    assert "耐克" in hint


def test_self_check_without_values_still_flags_retry():
    from app.agent.nodes import self_check as module

    result = run(module.self_check({"retrieved_value_infos": []}, make_runtime()))

    assert result["empty_retry_done"] is True
    assert "拼写与粒度" in result["self_check_hint"]
