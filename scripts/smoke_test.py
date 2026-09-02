"""
部署后端到端冒烟测试

在服务器上运行：uv run python scripts/smoke_test.py
对 /api/query 发起一次真实问数，逐事件打印进度并断言最终拿到 result。
退出码非 0 表示链路异常，可直接用于人工巡检或后续监控脚本。
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description="问数链路冒烟测试")
    parser.add_argument(
        "--host", default=os.getenv("SMOKE_HOST", "http://127.0.0.1:8000"),
        help="后端地址，默认 http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--query", default="统计华北地区的销售总额", help="冒烟用的问题"
    )
    args = parser.parse_args()

    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    # 服务器开启鉴权时，从环境变量读取令牌
    token = os.getenv("API_TOKEN", "")
    if token:
        headers["X-API-Token"] = token

    payload = json.dumps({"query": args.query, "history": []}).encode("utf-8")
    request = urllib.request.Request(
        f"{args.host.rstrip('/')}/api/query", data=payload, headers=headers, method="POST"
    )

    started = time.monotonic()
    got_result = False
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:"):].strip())
                elapsed = round(time.monotonic() - started, 1)
                if event.get("type") == "progress":
                    print(f"[{elapsed:>7.1f}s] {event['step']} -> {event['status']}")
                elif event.get("type") == "result":
                    got_result = True
                    print(f"[{elapsed:>7.1f}s] RESULT: {event['data']}")
                    break
                elif event.get("type") == "error":
                    print(f"[{elapsed:>7.1f}s] ERROR: {event['message']}")
                    sys.exit(1)
    except urllib.error.HTTPError as error:
        print(f"HTTP {error.code}: {error.read().decode('utf-8', 'ignore')[:200]}")
        sys.exit(1)

    if not got_result:
        print("未收到 result 事件，冒烟测试失败")
        sys.exit(1)

    print(f"SMOKE_OK total={round(time.monotonic() - started, 1)}s")


if __name__ == "__main__":
    main()
