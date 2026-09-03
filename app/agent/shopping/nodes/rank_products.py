"""
商品重排节点（导购链路）

确定性打分（不调 LLM）：语义匹配 + 评分 + 销量 + 预算契合 - 风险惩罚；
高风险商品不进入主推荐（M5.2 风险拦截），输出 top 5
"""

from langgraph.runtime import Runtime

from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.conf.app_config import app_config
from app.core.log import logger

# 风险等级惩罚系数：高风险大幅降权但不一票否决（风险已在推荐理由中如实呈现）
RISK_PENALTY = {"low": 0.0, "medium": 0.05, "high": 0.25, "unknown": 0.1}


async def rank_products(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """综合多因子给候选商品打分排序"""

    writer = runtime.stream_writer
    step = "商品排序"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        candidates = state.get("candidate_products") or []
        risk_summary = state.get("risk_summary") or {}
        slots = state.get("purchase_slots") or {}
        budget_max = slots.get("budget_max")
        top_k = app_config.shopping.rank_top_k
        semantic_floor = app_config.shopping.semantic_floor

        if not candidates:
            writer({"type": "progress", "step": step, "status": "success"})
            return {"ranked_products": []}

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

            # 预算契合：到手价不超预算满分；超出越多衰减越快
            effective_price = candidate.get("promotion_price") or candidate.get("price")
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
            ranked.append({**candidate, "final_score": round(score, 4)})

        # 风险拦截：存在非高风险候选时，剔除高风险商品（M5.2）
        non_high = [c for c in ranked if risk_summary.get(c["product_id"], {}).get("level") != "high"]
        pool = non_high if non_high else ranked
        pool.sort(key=lambda c: c["final_score"], reverse=True)
        ranked_products = pool[:top_k]

        logger.info(f"排序完成：{len(candidates)} -> {len(ranked_products)}，"
                    f"头部：{[(c['product_id'], c['final_score']) for c in ranked_products[:3]]}")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"ranked_products": ranked_products}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
