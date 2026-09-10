"""
部署后系统回归测试（回归报告第 7 节沉淀建议 / M8.6）

覆盖：认证、鉴权越权、SSE 追问/推荐、品型一致性、预算边界、
对比同源、文案不含后端 ID、会话 CRUD 与 stop 接口。
退出码非 0 表示回归失败，CI 部署后必跑。

用法（服务器上，或经 SSH 在服务器执行，与 CI 一致）：
  API_TOKEN=xxx uv run python scripts/regression_test.py
本机直连生产（默认 host 127.0.0.1:8000 是服务器本地 uvicorn，本机没有）：
  REGRESSION_HOST=http://服务器IP API_TOKEN=xxx uv run python scripts/regression_test.py
注意：本机不带这两个环境变量直接跑，所有用例必然失败，不代表线上故障。
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HOST = os.getenv("REGRESSION_HOST", "http://127.0.0.1:8000")
TOKEN = os.getenv("API_TOKEN", "")
PASSED = 0
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = ""):
    global PASSED
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" | {detail}" if detail and not ok else ""))
    if ok:
        PASSED += 1
    else:
        FAILED.append(name)


def request_json(method: str, path: str, body: dict | None = None, headers: dict | None = None):
    req = urllib.request.Request(
        f"{HOST}{path}",
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read().decode() or "{}")
        except Exception:  # noqa: BLE001
            return error.code, {}


def post_sse(payload: dict, jwt: str = "") -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-API-Token": TOKEN,
    }
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    req = urllib.request.Request(
        f"{HOST}/api/shopping/query",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    events = []
    with urllib.request.urlopen(req, timeout=150) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


def auth_headers(token: str) -> dict:
    return {"X-API-Token": TOKEN, "Authorization": f"Bearer {token}"}


def main() -> None:
    if not TOKEN:
        print("缺少 API_TOKEN")
        sys.exit(2)

    stamp = str(int(time.time()))
    user_a = f"rega_{stamp}"
    user_b = f"regb_{stamp}"
    pwd = "regtest123456"

    # ---------- 认证 ----------
    code, body = request_json("POST", "/api/auth/register", {"username": user_a, "password": pwd})
    check("注册用户A", code == 200 and body.get("token"), f"HTTP {code}")
    jwt_a = body.get("token", "")
    code, _ = request_json("POST", "/api/auth/register", {"username": user_a, "password": pwd})
    check("重复用户名 409", code == 409, f"HTTP {code}")
    code, body = request_json("POST", "/api/auth/register", {"username": user_b, "password": pwd})
    jwt_b = body.get("token", "")
    check("注册用户B", code == 200 and jwt_b, f"HTTP {code}")
    code, body = request_json("POST", "/api/auth/login", {"username": user_a, "password": "wrong"})
    check("错误密码 401", code == 401, f"HTTP {code}")

    # ---------- N12.33：管理台身份探测不抛错 ----------
    code, body = request_json("GET", "/api/admin/whoami", None, auth_headers(jwt_a))
    check("管理台 whoami 非管理员", code == 200 and body.get("admin") is False, f"HTTP {code} {body}")
    code, body = request_json("GET", "/api/admin/whoami", None, {"X-API-Token": TOKEN})
    check("管理台 whoami 未登录", code == 200 and body.get("admin") is False, f"HTTP {code}")

    # ---------- 鉴权 ----------
    code, _ = request_json("POST", "/api/shopping/query", {"query": "测试"})
    check("无凭证访问导购 401", code == 401, f"HTTP {code}")

    # ---------- SSE：模糊需求追问 ----------
    events = post_sse({"query": "帮我推荐点好东西"})
    check("模糊需求触发追问", any(e.get("type") == "clarification" for e in events))

    # ---------- SSE：品型一致性（空气炸锅） ----------
    history: list[dict] = []
    session_id = ""
    recommendation = None
    for rnd in range(3):
        events = post_sse(
            {
                "query": "想买个空气炸锅，两个人用" if rnd == 0 else "跳过",
                "history": history,
                **({"session_id": session_id} if session_id else {}),
            },
            jwt=jwt_a,
        )
        recommendation = next((e for e in events if e.get("type") == "recommendation"), None)
        if recommendation:
            session_id = recommendation.get("session_id", session_id)
            break
        cla = next((e for e in events if e.get("type") == "clarification"), None)
        if not cla:
            break
        history += [
            {"role": "user", "content": "想买个空气炸锅，两个人用"},
            {"role": "assistant", "content": cla["question"]},
            {"role": "user", "content": "跳过"},
        ][-4:]

    products = (recommendation or {}).get("recommended_products") or []
    summary = (recommendation or {}).get("summary", "")
    check("空气炸锅需求返回推荐", recommendation is not None)
    check(
        "品型一致性：只推荐空气炸锅",
        bool(products) and all("空气炸锅" in p.get("title", "") for p in products),
        str([p.get("title", "")[:12] for p in products]),
    )
    if len(products) < 3:
        check("候选不足时明示", "候选不足" in summary, summary[:60])
    # F-REG-003：用户可见文案不出现后端 ID
    visible_text = summary + "".join(p.get("title", "") + p.get("reason", "") for p in products)
    check("文案不含后端 ID", not re.search(r"P\d{4}", visible_text))

    # ---------- 普通推荐轮不自动发对比（回归 8.3-2） ----------
    check(
        "普通推荐不自动发送对比表",
        not any(e.get("type") == "comparison" for e in events),
    )

    # ---------- 预算边界 ----------
    history2: list[dict] = []
    for rnd in range(3):
        events2 = post_sse(
            {
                "query": "预算300以内的厨房小电器" if rnd == 0 else "跳过",
                "history": history2,
            }
        )
        rec2 = next((e for e in events2 if e.get("type") == "recommendation"), None)
        if rec2:
            prices = [p.get("promotion_price") or p.get("price") or 0 for p in rec2["recommended_products"]]
            check("预算300边界", all(p <= 300 for p in prices), str(prices))
            break
        cla = next((e for e in events2 if e.get("type") == "clarification"), None)
        if not cla:
            check("预算300边界", False, "未返回推荐")
            break
        history2 += [
            {"role": "user", "content": "预算300以内的厨房小电器"},
            {"role": "assistant", "content": cla["question"]},
            {"role": "user", "content": "跳过"},
        ][-4:]

    # ---------- 边界校验 ----------
    code, _ = request_json(
        "POST", "/api/shopping/query", {"query": "长" * 501}, {"X-API-Token": TOKEN}
    )
    check("query 超长 422", code == 422, f"HTTP {code}")
    code, _ = request_json(
        "POST",
        "/api/shopping/query",
        {"query": "测试", "history": [{"role": "user", "content": "x"}] * 7},
        {"X-API-Token": TOKEN},
    )
    check("history 超条 422", code == 422, f"HTTP {code}")

    # ---------- 主动对比：集合来自推荐集合 ----------
    if len(products) >= 2:
        ids = [p["product_id"] for p in products[:2]]
    else:
        ids = ["P0001", "P0002"]
    cmp_events = post_sse({"query": "对比这两款", "selected_product_ids": ids})
    cmp_event = next((e for e in cmp_events if e.get("type") == "comparison"), None)
    check("主动对比返回对比表", cmp_event is not None)
    if cmp_event:
        cmp_ids = {r.get("product_id") for r in cmp_event["table"]["rows"]}
        check("对比集合来自指定商品", set(ids) == cmp_ids, f"{ids} vs {cmp_ids}")

    # ---------- N11.33：显式选品不被预算/品类过滤误杀 ----------
    cmp_events2 = post_sse(
        {
            "query": "帮我对比这 2 款商品，预算200以内",
            "selected_product_ids": ["P0004", "P0005"],
        }
    )
    cmp_event2 = next((e for e in cmp_events2 if e.get("type") == "comparison"), None)
    if cmp_event2:
        cmp_ids2 = {r.get("product_id") for r in cmp_event2["table"]["rows"]}
        check(
            "N11.33 超预算选品不被剔除",
            cmp_ids2 == {"P0004", "P0005"},
            f"P0004/P0005 vs {cmp_ids2}",
        )
    else:
        check("N11.33 超预算选品不被剔除", False, "未返回对比表")

    # ---------- N11.32：显式品型无货禁止相邻品类冒充 ----------
    rec3: dict | None = None
    history3: list[dict] = []
    ear_query = "想买一个蓝牙耳机，预算300以内，通勤使用"
    for rnd in range(3):
        events3 = post_sse({"query": ear_query if rnd == 0 else "跳过", "history": history3})
        rec3 = next((e for e in events3 if e.get("type") == "recommendation"), None)
        if rec3:
            break
        cla3 = next((e for e in events3 if e.get("type") == "clarification"), None)
        if not cla3:
            break
        history3 += [
            {"role": "user", "content": ear_query},
            {"role": "assistant", "content": cla3["question"]},
            {"role": "user", "content": "跳过"},
        ][-4:]
    ear_products = (rec3 or {}).get("recommended_products") or []
    ear_summary = (rec3 or {}).get("summary", "")
    check(
        "N11.32 耳机无货返回空推荐",
        ear_products == [],
        str([p.get("title", "")[:12] for p in ear_products]),
    )
    check("N11.32 空结果明示暂无品型", "暂无「耳机」" in ear_summary, ear_summary[:60])
    relax_events = post_sse(
        {
            "query": "没有耳机的话，推荐最接近的品类",
            "history": history3 + [{"role": "assistant", "content": ear_summary[:200]}],
        }
    )
    relax_rec = next((e for e in relax_events if e.get("type") == "recommendation"), None)
    relax_products = (relax_rec or {}).get("recommended_products") or []
    check(
        "N11.32 放宽表述解锁相近品类",
        bool(relax_products),
        str([p.get("title", "")[:12] for p in relax_products]),
    )

    # ---------- 会话 CRUD + 越权 ----------
    code, body = request_json("GET", "/api/shopping/sessions", None, auth_headers(jwt_a))
    check("用户A会话列表", code == 200 and isinstance(body, list))
    if session_id:
        code, _ = request_json("GET", f"/api/shopping/sessions/{session_id}", None, auth_headers(jwt_b))
        check("跨用户读详情 404", code == 404, f"HTTP {code}")
        code, _ = request_json("POST", f"/api/shopping/sessions/{session_id}/stop", None, auth_headers(jwt_a))
        check("stop 接口（属主）", code == 200, f"HTTP {code}")
        code, _ = request_json("POST", f"/api/shopping/sessions/{session_id}/stop", None, auth_headers(jwt_b))
        check("跨用户 stop 404", code == 404, f"HTTP {code}")
        code, body = request_json("GET", f"/api/shopping/sessions/{session_id}", None, auth_headers(jwt_a))
        check("停止后详情仍可读（状态 stopped）", code == 200)
        code, _ = request_json("DELETE", f"/api/shopping/sessions/{session_id}", None, auth_headers(jwt_b))
        check("跨用户删除 404", code == 404, f"HTTP {code}")
        code, _ = request_json("DELETE", f"/api/shopping/sessions/{session_id}", None, auth_headers(jwt_a))
        check("属主删除会话", code == 200, f"HTTP {code}")
        code, _ = request_json("GET", f"/api/shopping/sessions/{session_id}", None, auth_headers(jwt_a))
        check("删除后读取 404", code == 404, f"HTTP {code}")

    # ---------- 汇总 ----------
    total = PASSED + len(FAILED)
    print(f"\n回归结果：{PASSED}/{total} 通过")
    if FAILED:
        print("失败项：", "、".join(FAILED))
        print("REGRESSION_FAILED")
        sys.exit(1)
    print("REGRESSION_OK")


if __name__ == "__main__":
    main()
