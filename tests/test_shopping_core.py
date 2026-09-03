"""
配置与评测数据集的完整性测试
"""

from pathlib import Path

import yaml


def test_app_config_has_shopping_section():
    from app.conf.app_config import app_config

    assert app_config.shopping.recall_limit > 0
    assert 0 < app_config.shopping.semantic_floor < 1
    assert app_config.shopping.rank_top_k > 0


def test_shopping_graph_compiles():
    from app.agent.shopping.graph import shopping_graph

    nodes = [n for n in shopping_graph.get_graph().nodes if not n.startswith("__")]
    assert len(nodes) == 10
    assert "recall_products" in nodes
    assert "generate_recommendation" in nodes


def test_shopping_eval_dataset_valid():
    """评测集结构完整：id 唯一、必填字段齐全、品类合法"""

    cases = yaml.safe_load(
        (Path(__file__).parents[1] / "evals" / "shopping_questions.yaml").read_text(
            encoding="utf-8"
        )
    )
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids)), "评测用例 id 重复"
    for case in cases:
        assert case.get("category") in {"推荐", "对比", "避坑", "追问"}
        assert case.get("question") or case.get("turns"), f"{case['id']} 缺少问题"
        if case.get("turns"):
            for turn in case["turns"]:
                assert turn.get("question"), f"{case['id']} 多轮缺少轮次问题"
