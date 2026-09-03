"""
导购链路评测跑批

对 evals/shopping_questions.yaml 的每条用例发起真实 /api/shopping/query 请求，
按声明式 checks 断言事件流（结构完整性 + 事实锚定 + 验收标准），
输出分类准确率报告。PRD 第 15 节验收标准以 acceptance: true 标记。

用法（服务器项目根目录）：
    API_TOKEN=xxx uv run python evals/run_shopping_evals.py
    API_TOKEN=xxx uv run python evals/run_shopping_evals.py --ids s001,s014
    API_TOKEN=xxx uv run python evals/run_shopping_evals.py --category 追问

退出码：准确率低于阈值时非 0。
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from urllib import request

import yaml

sys.path.insert(0, str(Path(__file__).parents[1]))

QUESTIONS_FILE = Path(__file__).parent / "shopping_questions.yaml"


def stream_once(host: str, payload: dict, token: str, timeout: float):
    """发起一次导购请求，收集全部事件后返回"""

    req = request.Request(
        f"{host.rstrip('/')}/api/shopping/query",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "X-API-Token": token,
        },
        method="POST",
    )
    events = []
    with request.urlopen(req, timeout=timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:"):].strip()))
    return events


class CaseResult:
    """一次用例执行收集到的事件视图与断言结果"""

    def __init__(self):
        self.events: list[dict] = []
        self.error: str | None = None

    @property
    def recommendation(self) -> dict | None:
        for event in reversed(self.events):
            if event.get("type") == "recommendation":
                return event
        return None

    @property
    def comparison(self) -> dict | None:
        for event in reversed(self.events):
            if event.get("type") == "comparison":
                return event
        return None

    @property
    def clarification(self) -> dict | None:
        for event in self.events:
            if event.get("type") == "clarification":
                return event
        return None

    @property
    def recommended(self) -> list[dict]:
        return (self.recommendation or {}).get("recommended_products") or []

    def run_checks(self, checks: dict) -> list[str]:
        """执行声明式断言，返回失败的检查描述"""

        failures = []
        products = self.recommended
        reasons = [p.get("reason", "") for p in products]

        if "recommended_min" in checks and len(products) < checks["recommended_min"]:
            failures.append(f"推荐商品数 {len(products)} < {checks['recommended_min']}")

        if "contains_product" in checks:
            ids = {p["product_id"] for p in products}
            if checks["contains_product"] not in ids:
                failures.append(f"推荐未包含 {checks['contains_product']}（实际 {sorted(ids)}）")

        if "excludes_product" in checks:
            ids = {p["product_id"] for p in products}
            if checks["excludes_product"] in ids:
                failures.append(f"推荐不应包含 {checks['excludes_product']}")

        if "all_category" in checks and products:
            bad = [p["product_id"] for p in products if p.get("category_name") != checks["all_category"]]
            if bad:
                failures.append(f"品类不符 {checks['all_category']}：{bad}")

        if "max_price" in checks and products:
            over = [
                f"{p['product_id']}¥{p.get('promotion_price') or p.get('price')}"
                for p in products
                if (p.get("promotion_price") or p.get("price") or 0) > checks["max_price"]
            ]
            if over:
                failures.append(f"超出预算 {checks['max_price']}：{over}")

        if checks.get("reasons_nonempty") and products and not all(reasons):
            failures.append("存在空推荐理由")

        if checks.get("mentions_risk"):
            risk_keywords = ("噪音", "风险", "差评", "注意", "虚标", "异味", "发热", "谨慎")
            summary = (self.recommendation or {}).get("summary", "")
            hit = any(any(k in r for k in risk_keywords) for r in reasons) or any(
                k in summary for k in risk_keywords
            )
            if not hit:
                failures.append("风险商品未提及风险提示")

        if checks.get("muying_caution") and products:
            caution_keywords = ("认证", "资质", "月龄", "核对")
            lacking = [
                p["product_id"]
                for p, r in zip(products, reasons)
                if p.get("category_name") == "母婴用品" and not any(k in r for k in caution_keywords)
            ]
            if lacking:
                failures.append(f"母婴推荐缺谨慎话术：{lacking}")

        if "comparison_min_rows" in checks:
            rows = (self.comparison or {}).get("table", {}).get("rows", [])
            if len(rows) < checks["comparison_min_rows"]:
                failures.append(f"对比行数 {len(rows)} < {checks['comparison_min_rows']}")

        if "text_intent_comparison" in checks:
            wanted = set(checks["text_intent_comparison"])
            rows = (self.comparison or {}).get("table", {}).get("rows", [])
            row_ids = {row.get("product_id") for row in rows}
            ids_in_reasons = {p["product_id"] for p in products}
            if len(rows) < 2 and not wanted.issubset(ids_in_reasons) and not wanted & row_ids:
                failures.append(f"文本对比未覆盖 {sorted(wanted)}")

        return failures


def evaluate_case(case: dict, results: list[CaseResult]) -> list[str]:
    """对一次用例的全部轮次结果执行断言，返回失败明细"""

    failures: list[str] = []
    turns = case.get("turns") or [case]
    for index, (turn, result) in enumerate(zip(turns, results), start=1):
        prefix = f"轮{index}" if len(turns) > 1 else ""

        expected = turn.get("expect")
        if expected == "clarification" and result.clarification is None:
            failures.append(f"{prefix}应追问却未追问")
        if expected == "recommendation" and result.recommendation is None:
            failures.append(f"{prefix}应推荐却未推荐")
        if result.error:
            failures.append(f"{prefix}链路错误：{result.error[:80]}")

        failures.extend(f"{prefix}{f}" if prefix else f for f in result.run_checks(turn.get("checks") or {}))

        # 验收项：完整多轮以推荐收尾时，末轮必须满足推荐类验收
        if case.get("acceptance") and index == len(turns) and result.recommendation is not None:
            if len(result.recommended) < 3:
                failures.append(f"{prefix}验收：推荐商品数 {len(result.recommended)} < 3")
            if not all(p.get("reason", "").strip() for p in result.recommended):
                failures.append(f"{prefix}验收：存在空理由推荐")

    return failures


async def run_case(case: dict, host: str, token: str, timeout: float) -> tuple[bool, str, float]:
    """执行一条用例（可能多轮），返回 (通过, 明细, 耗时)"""

    started = time.monotonic()
    turns = case.get("turns") or [case]
    results: list[CaseResult] = []
    history: list[dict] = []
    session_id = ""
    clarification_count = 0

    try:
        for turn in turns:
            payload = {
                "query": turn["question"],
                "history": history,
                "clarification_count": clarification_count,
            }
            if turn.get("selected_product_ids"):
                payload["selected_product_ids"] = turn["selected_product_ids"]
            if session_id:
                payload["session_id"] = session_id

            result = CaseResult()
            result.events = await asyncio.to_thread(
                stream_once, host, payload, token, timeout
            )
            results.append(result)

            # 从事件流提取多轮上下文：session、追问计数、文本历史
            for event in result.events:
                if event.get("type") in ("progress", "recommendation", "clarification"):
                    session_id = event.get("session_id", session_id)
                if event.get("type") == "clarification":
                    clarification_count = event.get("clarification_count", clarification_count)

            # 助手侧文本：追问用问题本身，推荐用总结
            assistant_content = (
                result.clarification.get("question", "")
                if result.clarification is not None
                else (result.recommendation or {}).get("summary", "")
            )
            history = (history + [
                {"role": "user", "content": turn["question"]},
                {"role": "assistant", "content": assistant_content[:200]},
            ])[-6:]
    except Exception as exc:  # noqa: BLE001
        return False, f"链路异常：{type(exc).__name__}: {str(exc)[:100]}", round(time.monotonic() - started, 1)

    failures = evaluate_case(case, results)
    detail = "通过" if not failures else "；".join(failures[:3])
    return not failures, detail, round(time.monotonic() - started, 1)


async def main():
    parser = argparse.ArgumentParser(description="导购链路评测跑批")
    parser.add_argument("--ids", default="", help="逗号分隔用例 id")
    parser.add_argument("--category", default="", help="只跑指定分类")
    parser.add_argument("--timeout", type=float, default=300, help="单轮超时秒数")
    parser.add_argument("--threshold", type=float, default=0.85, help="准确率阈值")
    parser.add_argument(
        "--host", default="http://127.0.0.1:8000", help="后端地址"
    )
    args = parser.parse_args()

    token = os.environ.get("API_TOKEN", "")
    if not token:
        print("缺少 API_TOKEN 环境变量")
        sys.exit(2)

    cases = yaml.safe_load(QUESTIONS_FILE.read_text(encoding="utf-8"))
    if args.ids:
        wanted = {item.strip() for item in args.ids.split(",") if item.strip()}
        cases = [c for c in cases if c["id"] in wanted]
    if args.category:
        cases = [c for c in cases if c["category"] == args.category]
    if not cases:
        print("没有匹配的用例")
        sys.exit(2)

    print(f"导购评测用例 {len(cases)} 条，阈值 {args.threshold:.0%}\n")

    passed = 0
    by_category: dict[str, list[bool]] = {}
    failures: list[str] = []

    for index, case in enumerate(cases, start=1):
        ok, detail, elapsed = await run_case(case, args.host, token, args.timeout)
        # 链路类失败重试一次（与问数评测同策略）
        if not ok and ("链路异常" in detail or "超时" in detail):
            ok, detail, elapsed = await run_case(case, args.host, token, args.timeout)

        passed += int(ok)
        by_category.setdefault(case["category"], []).append(ok)
        mark = "PASS" if ok else "FAIL"
        print(f"[{index:>2}/{len(cases)}] {mark} {case['id']} ({case['category']}) {elapsed:>6.1f}s | {detail}")
        if not ok:
            failures.append(case["id"])

    accuracy = passed / len(cases)
    print("\n========== 导购评测报告 ==========")
    for category, results in by_category.items():
        print(f"  {category}: {sum(results)}/{len(results)} ({sum(results) / len(results):.0%})")
    acceptance_total = [c for c in cases if c.get("acceptance")]
    if acceptance_total:
        print(f"  含验收用例 {len(acceptance_total)} 条（PRD 第 15 节）")
    print(f"  总体: {passed}/{len(cases)} ({accuracy:.0%}，阈值 {args.threshold:.0%})")
    if failures:
        print(f"  失败用例: {', '.join(failures)}")

    if accuracy < args.threshold:
        print("EVAL_FAILED")
        sys.exit(1)
    print("EVAL_OK")


if __name__ == "__main__":
    import os

    asyncio.run(main())
