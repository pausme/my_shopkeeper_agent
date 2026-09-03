"""
问数链路评测跑批

对 evals/questions.yaml 中的每条用例执行完整智能体链路（含真实 LLM 调用），
把执行结果与 expect_sql 的结果集对比，输出分类准确率报告。

用法（在服务器项目根目录执行）：
    uv run python evals/run_evals.py                 # 全量
    uv run python evals/run_evals.py --smoke         # 只跑冒烟子集
    uv run python evals/run_evals.py --ids q001,q002 # 指定用例
    uv run python evals/run_evals.py --category 指标口径 --threshold 0.9

退出码：准确率低于阈值时非 0，可直接作为 CI 门禁。
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

import yaml

# 以脚本方式运行时把项目根加入 sys.path，使 app 包可导入
sys.path.insert(0, str(Path(__file__).parents[1]))

from app.agent.context import DataAgentContext  # noqa: E402
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    dw_mysql_client_manager,
    meta_mysql_client_manager,
)
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

QUESTIONS_FILE = Path(__file__).parent / "questions.yaml"


def normalize_value(value):
    """结果值归一化：数值保留两位小数，None/空串统一为 "-"，其余转字符串去首尾空格"""

    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        rounded = round(float(value), 2)
        return f"{rounded:.2f}"
    text = str(value).strip()
    return text if text else "-"


def normalize_rows(rows, ordered: bool) -> list[tuple[str, ...]]:
    """行归一化：忽略列名（模型起别名可能不同），按值比较；默认忽略行序"""

    normalized = [tuple(normalize_value(v) for v in row.values()) for row in rows]
    return normalized if ordered else sorted(normalized)


async def run_case(case: dict, context: DataAgentContext, dw: DWMySQLRepository, timeout: float):
    """跑一条用例，返回 (是否通过, 摘要信息, 耗时)"""

    started = time.monotonic()
    result_data = None
    error_message = None
    generated_sql = None

    async def consume():
        nonlocal result_data, error_message, generated_sql
        state = DataAgentState(query=case["question"], history=case.get("history") or [])
        async for mode, chunk in graph.astream(
            input=state, context=context, stream_mode=["custom", "updates"]
        ):
            if mode == "custom":
                if chunk.get("type") == "result":
                    result_data = chunk.get("data")
                elif chunk.get("type") == "error":
                    error_message = chunk.get("message")
            elif mode == "updates":
                # 记录最后一次写入的 SQL，便于报告对照
                for delta in chunk.values():
                    if isinstance(delta, dict) and "sql" in delta:
                        generated_sql = delta["sql"]

    try:
        await asyncio.wait_for(consume(), timeout=timeout)
    except asyncio.TimeoutError:
        return False, f"单用例超时（>{timeout:.0f}s）", round(time.monotonic() - started, 1)
    except Exception as exc:  # noqa: BLE001
        # 供应商断连等链路异常只判本条失败，不能让整批评测崩溃
        return (
            False,
            f"链路异常：{type(exc).__name__}: {str(exc)[:120]}",
            round(time.monotonic() - started, 1),
        )

    if error_message:
        return False, f"链路错误：{error_message[:120]}", round(time.monotonic() - started, 1)
    if result_data is None:
        return False, "未收到结果事件", round(time.monotonic() - started, 1)

    try:
        expected = await dw.run(case["expect_sql"].strip())
    except Exception as exc:  # noqa: BLE001
        return False, f"标准 SQL 执行失败：{exc}", round(time.monotonic() - started, 1)

    actual_rows = normalize_rows(
        result_data if isinstance(result_data, list) else [result_data],
        case.get("ordered", False),
    )
    expected_rows = normalize_rows(expected, case.get("ordered", False))

    if actual_rows == expected_rows:
        return True, "通过", round(time.monotonic() - started, 1)
    return (
        False,
        f"结果不一致\n      实际: {actual_rows[:3]}\n      期望: {expected_rows[:3]}\n      SQL: {(generated_sql or '').strip().replace(chr(10), ' ')[:160]}",
        round(time.monotonic() - started, 1),
    )


async def main():
    parser = argparse.ArgumentParser(description="问数链路评测跑批")
    parser.add_argument("--ids", default="", help="逗号分隔的用例 id 列表")
    parser.add_argument("--category", default="", help="只跑指定分类")
    parser.add_argument("--smoke", action="store_true", help="只跑冒烟子集")
    parser.add_argument("--limit", type=int, default=0, help="最多跑前 N 条")
    parser.add_argument("--timeout", type=float, default=300, help="单用例超时秒数")
    parser.add_argument("--threshold", type=float, default=0.85, help="准确率阈值")
    args = parser.parse_args()

    cases = yaml.safe_load(QUESTIONS_FILE.read_text(encoding="utf-8"))
    if args.ids:
        wanted = {item.strip() for item in args.ids.split(",") if item.strip()}
        cases = [case for case in cases if case["id"] in wanted]
    if args.category:
        cases = [case for case in cases if case["category"] == args.category]
    if args.smoke:
        cases = [case for case in cases if case.get("smoke")]
    if args.limit:
        cases = cases[: args.limit]

    if not cases:
        print("没有匹配的用例")
        sys.exit(2)

    print(f"评测用例 {len(cases)} 条，阈值 {args.threshold:.0%}，开始执行...\n")

    # 初始化全部基础设施客户端（与 build_meta_knowledge 相同的依赖面）
    qdrant_client_manager.init()
    embedding_client_manager.init()
    es_client_manager.init()
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()

    passed = 0
    by_category: dict[str, list[bool]] = {}
    failures: list[str] = []

    async with (
        meta_mysql_client_manager.session_factory() as meta_session,
        dw_mysql_client_manager.session_factory() as dw_session,
    ):
        context = DataAgentContext(
            column_qdrant_repository=ColumnQdrantRepository(qdrant_client_manager.client),
            embedding_client=embedding_client_manager.client,
            metric_qdrant_repository=MetricQdrantRepository(qdrant_client_manager.client),
            value_es_repository=ValueESRepository(es_client_manager.client),
            meta_mysql_repository=MetaMySQLRepository(meta_session),
            dw_mysql_repository=DWMySQLRepository(dw_session),
        )

        for index, case in enumerate(cases, start=1):
            ok, detail, elapsed = await run_case(case, context, context["dw_mysql_repository"], args.timeout)
            # 供应商断连/超时等链路抖动导致的失败重试一次：
            # 真实的质量问题会连挂两次，网络抖动通常第二次即过
            if not ok and ("链路异常" in detail or "超时" in detail):
                ok, detail, elapsed = await run_case(
                    case, context, context["dw_mysql_repository"], args.timeout
                )
            passed += int(ok)
            by_category.setdefault(case["category"], []).append(ok)
            mark = "PASS" if ok else "FAIL"
            print(f"[{index:>2}/{len(cases)}] {mark} {case['id']} ({case['category']}) {elapsed:>6.1f}s | {detail}")
            if not ok:
                failures.append(case["id"])

    await qdrant_client_manager.close()
    await es_client_manager.close()
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()

    accuracy = passed / len(cases)
    print("\n========== 评测报告 ==========")
    for category, results in by_category.items():
        rate = sum(results) / len(results)
        print(f"  {category}: {sum(results)}/{len(results)} ({rate:.0%})")
    print(f"  总体: {passed}/{len(cases)} ({accuracy:.0%}，阈值 {args.threshold:.0%})")
    if failures:
        print(f"  失败用例: {', '.join(failures)}")

    if accuracy < args.threshold:
        print("EVAL_FAILED")
        sys.exit(1)
    print("EVAL_OK")


if __name__ == "__main__":
    asyncio.run(main())
