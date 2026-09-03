"""
商品重排节点（导购链路）

确定性打分（不调 LLM）：语义匹配 + 评分 + 销量 + 预算契合 - 风险惩罚；
硬性规则：库存拦截、超预算 30% 过滤、高风险拦截（PRD 10.4 / 15.2）；
为每款商品标注推荐结论：最推荐 / 预算优先 / 品质优先 / 谨慎购买（PRD 10.5）
"""

import time

from langgraph.runtime import Runtime

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

        # 排除条件程序化执行（PRD 10.1）：品牌精确匹配或标题包含排除词的商品直接剔除
        if exclusions:
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

        # 品类硬约束：槽位明确且同品类候选充足时，跨品类商品不参与排序
        category = slots.get("category")
        if category:
            same_category = [c for c in candidates if c.get("category_name") == category]
            if len(same_category) >= 3:
                candidates = same_category

        # 语义地板分：过滤明显跑题候选；过滤后不足 3 款则保留原候选
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

            # 预算硬过滤：超预算 30% 以上默认不展示（PRD 10.4）
            if budget_max and effective_price > budget_max * 1.3:
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

        # 风险拦截：存在非高风险候选时，剔除高风险商品（M5.2）
        non_high = [c for c in ranked if risk_summary.get(c["product_id"], {}).get("level") != "high"]
        pool = non_high if non_high else ranked
        pool.sort(key=lambda c: c["final_score"], reverse=True)
        ranked_products = pool[:top_k]

        # 推荐结论（PRD 10.5）：确定性标注，LLM 与前端直接使用
        _assign_verdicts(ranked_products, risk_summary)

        logger.info(f"排序完成：{len(candidates)} -> {len(ranked_products)}，耗时 {time.monotonic() - started:.2f}s，"
                    f"头部：{[(c['product_id'], c['verdict']) for c in ranked_products[:3]]}")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"ranked_products": ranked_products}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
