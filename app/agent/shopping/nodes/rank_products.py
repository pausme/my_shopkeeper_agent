"""
商品重排节点（导购链路）

确定性打分（不调 LLM）：语义匹配 + 评分 + 销量 + 预算契合 - 风险惩罚；
硬性规则：库存拦截、超预算 30% 过滤、高风险拦截（PRD 10.4 / 15.2）；
为每款商品标注推荐结论：最推荐 / 预算优先 / 品质优先 / 谨慎购买（PRD 10.5）
"""

import time

from langgraph.runtime import Runtime

from app.agent.shopping.category_match import match_product_type, type_in_candidate
from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.conf.app_config import app_config
from app.core.log import logger

# 风险等级惩罚系数：高风险大幅降权但不一票否决（风险已在推荐理由中如实呈现）
RISK_PENALTY = {"low": 0.0, "medium": 0.05, "high": 0.25, "unknown": 0.1}


def _assign_verdicts(products: list[dict], risk_summary: dict) -> None:
    """为排序后的商品标注推荐结论（确定性规则，与 LLM 无关）"""

    for product in products:
        level = risk_summary.get(product["product_id"], {}).get("level", "unknown")
        product["verdict"] = "谨慎购买" if level in ("medium", "high") else ""

    # 综合分第一且非谨慎 → 最推荐
    for product in products:
        if not product["verdict"]:
            product["verdict"] = "最推荐"
            break

    # 到手价最低且未分配 → 预算优先
    unassigned = [p for p in products if not p["verdict"]]
    if unassigned:
        cheapest = min(unassigned, key=lambda p: p.get("promotion_price") or p.get("price") or 0)
        cheapest["verdict"] = "预算优先"

    # 评分最高且未分配 → 品质优先
    unassigned = [p for p in products if not p["verdict"]]
    if unassigned:
        best = max(unassigned, key=lambda p: float(p.get("rating") or 0))
        best["verdict"] = "品质优先"


async def rank_products(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """综合多因子给候选商品打分排序"""

    writer = runtime.stream_writer
    step = "商品排序"
    writer({"type": "progress", "step": step, "status": "running"})
    started = time.monotonic()

    try:
        candidates = state.get("candidate_products") or []
        risk_summary = state.get("risk_summary") or {}
        slots = state.get("purchase_slots") or {}
        budget_max = slots.get("budget_max")
        exclusions = [str(e).strip() for e in (slots.get("exclusions") or []) if str(e).strip()]
        top_k = app_config.shopping.rank_top_k
        semantic_floor = app_config.shopping.semantic_floor

        if not candidates:
            writer({"type": "progress", "step": step, "status": "success"})
            return {"ranked_products": []}

        # N11.33（对比链路）：用户显式点名的商品只做如实呈现，
        # 品型/品类/语义地板/预算/风险过滤一律不适用（曾把对比选中商品误剔除）
        explicit_ids = list(
            state.get("selected_product_ids") or slots.get("product_ids") or []
        )
        explicit = set(explicit_ids)

        # N11.32 补强：追问应答轮（query 是"通用/跳过"这类短答）时，LLM 改写
        # 可能丢失品型词——回退用最近一条用户原始提问兜底锁定品型
        # （负向放宽表述仍优先：query 在匹配文本最前，"没有X"不会被历史解锁）
        last_user_query = ""
        for message in reversed(state.get("history") or []):
            if message.get("role") == "user" and str(message.get("content", "")).strip():
                last_user_query = str(message["content"])
                break

        # 品型硬约束（findings #24）：用户点名具体品型（如"空气炸锅"）时，
        # 只保留标题/属性命中该品型的商品，宁缺毋滥——绝不用相邻品类凑数
        type_keyword = (
            None if explicit else match_product_type(
                state.get("query"), state.get("rewritten_query"), last_user_query
            )
        )
        insufficient_note = ""
        if type_keyword:
            type_matched = [
                c
                for c in candidates
                if type_in_candidate(
                    type_keyword, c.get("title") or "", str(c.get("attributes") or {})
                )
            ]
            if type_matched:
                candidates = type_matched
                if len(type_matched) < 3:
                    insufficient_note = (
                        f"同品类候选不足：目前符合「{type_keyword}」的商品只有 "
                        f"{len(type_matched)} 款，已如实推荐，未用相近品类凑数。"
                    )
                    logger.info(f"品型约束：{type_keyword} 仅 {len(type_matched)} 款候选")
            else:
                # N11.32：显式品型无匹配时返回空推荐并明示，
                # 不得拿相邻品类商品冒充；用户回复"没有X的话推荐最接近的"
                # （category_match 负向识别）后才解锁相邻品类
                logger.info(f"品型约束：{type_keyword} 无匹配候选，返回空推荐")
                writer({"type": "progress", "step": step, "status": "success"})
                return {
                    "ranked_products": [],
                    "insufficient_note": (
                        f"暂无「{type_keyword}」类商品，已停止推荐，没有拿相近品类凑数。"
                        f"如果你愿意看相近品类，回复「没有{type_keyword}的话，推荐最接近的品类」即可。"
                    ),
                }

        # 排除条件程序化执行（PRD 10.1）：品牌精确匹配或标题包含排除词的商品直接剔除
        # （显式选品对比不适用——用户点名商品时排除项来自历史轮，不应误杀）
        if exclusions and not explicit:
            candidates = [
                c
                for c in candidates
                if not any(
                    exclusion
                    for exclusion in exclusions
                    if exclusion == (c.get("brand") or "")
                    or exclusion in (c.get("title") or "")
                )
            ]

        # 品类硬约束：槽位明确且同品类候选充足时，跨品类商品不参与排序（显式选品豁免）
        category = slots.get("category")
        if category and not explicit:
            same_category = [c for c in candidates if c.get("category_name") == category]
            if len(same_category) >= 3:
                candidates = same_category

        # 语义地板分：过滤明显跑题候选；过滤后不足 3 款则保留原候选（显式选品豁免）
        if not explicit:
            on_topic = [c for c in candidates if float(c.get("semantic_score", 0)) >= semantic_floor]
            if len(on_topic) >= 3:
                candidates = on_topic

        max_sales = max((c.get("sales_30d") or 0) for c in candidates) or 1
        ranked = []
        for candidate in candidates:
            pid = candidate["product_id"]
            level = risk_summary.get(pid, {}).get("level", "unknown")
            effective_price = candidate.get("promotion_price") or candidate.get("price")

            # 库存与下架拦截（PRD 15.2：库存不足不进主推荐）
            if (candidate.get("stock") or 0) <= 0:
                continue

            # 预算硬过滤：超预算 30% 以上默认不展示（PRD 10.4；显式选品对比豁免）
            if budget_max and not explicit and effective_price > budget_max * 1.3:
                continue

            # 预算契合：到手价不超预算满分；超预算但未达硬过滤线的做标记（PRD 10.4 显式标记）
            budget_exceeded = bool(budget_max and effective_price > budget_max)
            if budget_max:
                overspend = max(0.0, effective_price - budget_max) / budget_max
                budget_fit = max(0.0, 1.0 - overspend * 1.5)
            else:
                budget_fit = 0.6  # 无预算约束给中性分

            score = (
                0.45 * float(candidate.get("semantic_score", 0.0))
                + 0.20 * (float(candidate.get("rating", 0.0)) / 5.0)
                + 0.15 * (float(candidate.get("sales_30d") or 0) / max_sales)
                + 0.20 * budget_fit
                - RISK_PENALTY.get(level, 0.15)
            )
            ranked.append(
                {**candidate, "final_score": round(score, 4), "budget_exceeded": budget_exceeded}
            )

        # 风险拦截：存在非高风险候选时，剔除高风险商品（M5.2；显式选品对比豁免——
        # 用户点名要对比的商品如实呈现，靠"谨慎购买"结论与风险提示兜底）
        if explicit:
            pool = ranked
        else:
            non_high = [c for c in ranked if risk_summary.get(c["product_id"], {}).get("level") != "high"]
            pool = non_high if non_high else ranked
        pool.sort(key=lambda c: c["final_score"], reverse=True)
        # 预算内候选充足时不再保留略超预算商品（超预算展示仅在预算内池太薄时兜底；显式选品豁免）
        if budget_max and not explicit:
            in_budget = [c for c in pool if not c.get("budget_exceeded")]
            if len(in_budget) >= 3:
                pool = in_budget
        if explicit:
            # 对比场景保持用户的选品顺序（SQL IN 查询不保序）
            order = {pid: i for i, pid in enumerate(explicit_ids)}
            pool.sort(key=lambda c: order.get(c["product_id"], 99))
        ranked_products = pool[:top_k]

        # 推荐结论（PRD 10.5）：确定性标注，LLM 与前端直接使用
        _assign_verdicts(ranked_products, risk_summary)

        logger.info(f"排序完成：{len(candidates)} -> {len(ranked_products)}，耗时 {time.monotonic() - started:.2f}s，"
                    f"头部：{[(c['product_id'], c['verdict']) for c in ranked_products[:3]]}")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"ranked_products": ranked_products, "insufficient_note": insufficient_note}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
