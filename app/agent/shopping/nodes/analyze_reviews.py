"""
评价与风险分析节点（导购链路）

读取预计算的风险摘要（差评占比/风险标签/好评关键词/适合人群），
并用 ES 检索每个商品最集中差评关键词下的真实评价作佐证
"""

import asyncio

from langgraph.runtime import Runtime

from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.core.log import logger


async def analyze_reviews(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """汇总候选商品的评价要点与风险摘要"""

    writer = runtime.stream_writer
    step = "分析评价与风险"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        product_repository = runtime.context["product_repository"]
        review_es = runtime.context["review_es_repository"]
        candidates = state.get("candidate_products") or []

        # 并发读取风险摘要
        summaries = await asyncio.gather(
            *(product_repository.get_risk_summary(c["product_id"]) for c in candidates)
        )

        risk_summary: dict = {}
        review_summary: dict = {}
        for candidate, summary in zip(candidates, summaries):
            pid = candidate["product_id"]
            if summary is None:
                risk_summary[pid] = {
                    "level": "unknown",
                    "summary": "暂无足够评价样本，风险未知。",
                    "risk_tags": [],
                    "suitable": "",
                    "not_suitable": "",
                }
                review_summary[pid] = {
                    "sample_size": 0,
                    "negative_tags": [],
                    "positive_keywords": "",
                    "negative_examples": [],
                }
                continue

            risk_summary[pid] = {
                "level": summary.risk_level,
                "summary": summary.risk_summary,
                "risk_tags": summary.risk_tags_json or [],
                "suitable": summary.suitable_for or "",
                "not_suitable": summary.not_suitable_for or "",
            }
            review_summary[pid] = {
                "sample_size": summary.sample_size,
                "negative_tags": summary.risk_tags_json or [],
                "positive_keywords": summary.positive_summary or "",
                "negative_examples": [],
            }

        # 为差评集中（medium/high）的商品取 1~2 条真实差评原文作佐证（M8：事实可追溯）
        async def fetch_examples(pid: str, tags: list[str]) -> list[str]:
            if not tags:
                return []
            docs = await review_es.search_negative(pid, tags[0], limit=2)
            return [doc["content"] for doc in docs]

        example_tasks = [
            fetch_examples(c["product_id"], risk_summary[c["product_id"]]["risk_tags"])
            for c in candidates
            if risk_summary[c["product_id"]]["level"] in ("medium", "high")
        ]
        examples = await asyncio.gather(*example_tasks) if example_tasks else []
        example_iter = iter(examples)
        for c in candidates:
            pid = c["product_id"]
            if risk_summary[pid]["level"] in ("medium", "high"):
                review_summary[pid]["negative_examples"] = next(example_iter, [])

        logger.info(f"评价与风险分析完成：{len(candidates)} 款商品")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"risk_summary": risk_summary, "review_summary": review_summary}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
