"""
对比表构建节点（导购链路）

纯数据组装（不调 LLM）：取排序前 3 的商品，横向对比价格/评分/销量/关键属性/风险/适合人群
"""

from langgraph.runtime import Runtime

from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.core.log import logger

COMPARE_LIMIT = 3


async def build_comparison(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """组装前 3 名商品的横向对比表"""

    writer = runtime.stream_writer
    step = "构建对比"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        ranked = (state.get("ranked_products") or [])[:COMPARE_LIMIT]
        risk_summary = state.get("risk_summary") or {}
        review_summary = state.get("review_summary") or {}

        rows = []
        for product in ranked:
            pid = product["product_id"]
            risk = risk_summary.get(pid, {})
            attrs = product.get("attributes") or {}
            rows.append(
                {
                    "product_id": pid,
                    "商品": product["title"],
                    "到手价": f"{product.get('promotion_price') or product.get('price')} 元",
                    "评分": f"{product.get('rating')}（月销 {product.get('sales_30d')}）",
                    "关键属性": "；".join(f"{k}:{v}" for k, v in list(attrs.items())[:4]),
                    "好评关键词": review_summary.get(pid, {}).get("positive_keywords", ""),
                    "风险提示": risk.get("summary", ""),
                    "适合人群": risk.get("suitable", ""),
                    "不适合": risk.get("not_suitable", ""),
                }
            )

        logger.info(f"对比表构建完成：{len(rows)} 款商品")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"comparison_table": {"headers": list(rows[0].keys()) if rows else [], "rows": rows}}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
