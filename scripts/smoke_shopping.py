"""
导购链路冒烟测试

对 /api/shopping/query 发起两类真实请求并断言关键事件：
  1. 完整需求（品类+预算）→ 必须出现 recommendation 且至少 1 款带理由的商品
  2. 模糊需求 → 必须出现 clarification 追问
另验证 /feedback 落库。退出码非 0 表示链路异常。

用法：API_TOKEN=xxx uv run python scripts/smoke_shopping.py [--host http://127.0.0.1:8000]
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


def post_sse(host: str, path: str, payload: dict, token: str, timeout: float = 300):
    """POST 并逐行解析 SSE data 事件"""

    request = urllib.request.Request(
        f"{host.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "X-API-Token": token,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if line.startswith("data:"):
                yield json.loads(line[len("data:"):].strip())


def main():
    parser = argparse.ArgumentParser(description="导购链路冒烟测试")
    parser.add_argument("--host", default=os.getenv("SMOKE_HOST", "http://127.0.0.1:8000"))
    args = parser.parse_args()

    token = os.getenv("API_TOKEN", "")
    if not token:
        print("缺少 API_TOKEN 环境变量")
        sys.exit(2)

    failures = []

    # ---------- 用例 1：完整需求 → 推荐 ----------
    print("== 用例 1：完整需求应产出带理由的推荐 ==")
    started = time.monotonic()
    got_recommendation = False
    session_id = ""
    message_id = ""
    recommended_count = 0
    try:
        # 品类参数追问上线后，完整需求也可能先收到 clarification——自动用快捷选项续答
        query = "想买一个空气炸锅，预算500以内，帮我推荐一下"
        history: list[dict] = []
        clarification_count = 0
        for _round in range(3):
            events = list(
                post_sse(
                    args.host,
                    "/api/shopping/query",
                    {
                        "query": query,
                        "history": history,
                        "clarification_count": clarification_count,
                        **({"session_id": session_id} if session_id else {}),
                    },
                    token,
                )
            )
            recommendation = next((e for e in events if e["type"] == "recommendation"), None)
            clarification = next((e for e in events if e["type"] == "clarification"), None)
            error_event = next((e for e in events if e["type"] == "error"), None)

            if recommendation:
                got_recommendation = True
                session_id = recommendation.get("session_id", session_id)
                message_id = recommendation.get("message_id", "")
                recommended_count = len(recommendation.get("recommended_products", []))
                print(f"  推荐商品 {recommended_count} 款，summary: {recommendation.get('summary', '')[:50]}")
                break
            if clarification:
                options = [o for o in clarification.get("options", []) if o != "跳过"]
                query = options[0] if options else "跳过"
                session_id = clarification.get("session_id", session_id)
                clarification_count = clarification.get("clarification_count", clarification_count)
                history = history[-4:] + [
                    {"role": "assistant", "content": clarification.get("question", "")},
                    {"role": "user", "content": query},
                ]
                continue
            if error_event:
                failures.append(f"用例1链路错误：{error_event['message'][:100]}")
                break
    except Exception as exc:  # noqa: BLE001
        failures.append(f"用例1异常：{exc}")

    if not got_recommendation:
        failures.append("用例1未收到 recommendation 事件")
    elif recommended_count < 1:
        failures.append("用例1推荐商品数为 0")
    elif not session_id or not message_id:
        failures.append("用例1推荐事件缺少 session_id/message_id（反馈无法追溯）")
    print(f"  用时 {time.monotonic() - started:.0f}s -> {'PASS' if not failures else 'FAIL'}")

    # ---------- 用例 2：模糊需求 → 追问 ----------
    print("== 用例 2：模糊需求应触发追问 ==")
    got_clarification = False
    try:
        for event in post_sse(
            args.host, "/api/shopping/query", {"query": "帮我推荐点好东西"}, token
        ):
            if event["type"] == "clarification":
                got_clarification = True
                print(f"  追问: {event.get('question', '')[:60]}")
                break
            if event["type"] == "recommendation":
                failures.append("用例2模糊需求未追问直接推荐")
                break
    except Exception as exc:  # noqa: BLE001
        failures.append(f"用例2异常：{exc}")
    if not got_clarification:
        failures.append("用例2未收到 clarification 事件")
    print(f"  -> {'PASS' if got_clarification else 'FAIL'}")

    # ---------- 用例 3：反馈落库 ----------
    print("== 用例 3：反馈接口 ==")
    try:
        request = urllib.request.Request(
            f"{args.host.rstrip('/')}/api/shopping/feedback",
            data=json.dumps(
                {
                    "session_id": session_id or "SMOKE",
                    "message_id": message_id or None,
                    "feedback_type": "helpful",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-API-Token": token},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
            print(f"  feedback_id: {body.get('feedback_id')}")
            if not body.get("ok"):
                failures.append("用例3反馈返回 ok=false")
    except urllib.error.HTTPError as error:
        failures.append(f"用例3反馈 HTTP {error.code}")
    print("  -> PASS" if not any(f.startswith("用例3") for f in failures) else "  -> FAIL")

    if failures:
        print("\nSMOKE_SHOPPING_FAILED")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)
    print("\nSMOKE_SHOPPING_OK")


if __name__ == "__main__":
    main()
