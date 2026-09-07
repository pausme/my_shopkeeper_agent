"""
推荐生成节点（导购链路）

一次 LLM 调用生成整体结论与逐商品推荐理由；
理由强制锚定给定事实字段（价格/评分/销量/评价/风险），禁止编造（M8 幻觉兜底）
"""

import re

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from yaml import dump as yaml_dump

from app.agent.llm import llm
from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt

GENERIC_PRODUCT_ID_PATTERN = re.compile(r"(?<![A-Za-z0-9_])P\d{3,}(?![A-Za-z0-9_])")


def sanitize_visible_text(text: object, product_ids: set[str] | None = None) -> str:
    """移除用户可见文案中的内部商品编号，保留接口结构里的 product_id。"""

    cleaned = str(text or "")
    for product_id in sorted(product_ids or set(), key=len, reverse=True):
        cleaned = cleaned.replace(product_id, "")
    cleaned = GENERIC_PRODUCT_ID_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"（\s*）|\(\s*\)", "", cleaned)
    return cleaned.strip()


async def generate_recommendation(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """基于排序结果生成可解释推荐"""

    writer = runtime.stream_writer
    step = "生成推荐"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        ranked = state.get("ranked_products") or []
        risk_summary = state.get("risk_summary") or {}
        query = state.get("rewritten_query") or state["query"]

        if not ranked:
            writer({"type": "progress", "step": step, "status": "success"})
            return {
                "recommendation": {
                    "summary": "没有找到匹配的商品，请尝试放宽品类或预算条件。",
                    "recommendations": [],
                    "next_question": "",
                }
            }

        # 商品事实块：只喂给模型可追溯的字段
        facts_lines = []
        for index, product in enumerate(ranked, start=1):
            pid = product["product_id"]
            risk = risk_summary.get(pid, {})
            facts_lines.append(
                f"{index}. product_id={pid}\n"
                f"   标题：{product['title']}（品牌：{product.get('brand') or '无'}）\n"
                f"   到手价：{product.get('promotion_price') or product.get('price')} 元，"
                f"评分：{product.get('rating')}，近30天销量：{product.get('sales_30d')}\n"
                f"   属性：{product.get('attributes')}\n"
                f"   好评要点：{risk.get('suitable') and '' or ''}"
                f"{(state.get('review_summary') or {}).get(pid, {}).get('positive_keywords', '')}\n"
                f"   风险：[{risk.get('level', 'unknown')}] {risk.get('summary', '')}\n"
                f"   适合：{risk.get('suitable', '')}；不适合：{risk.get('not_suitable', '')}"
            )
        products_facts = "\n".join(facts_lines)

        prompt = PromptTemplate(
            template=load_prompt("generate_recommendation"),
            input_variables=["query", "slots", "products_facts"],
        )
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = await chain.ainvoke(
            {
                "query": query,
                "slots": yaml_dump(
                    state.get("purchase_slots") or {}, allow_unicode=True, sort_keys=False
                ),
                "products_facts": products_facts,
            }
        )
        if not isinstance(result, dict) or "recommendations" not in result:
            raise ValueError(f"推荐输出结构异常：{str(result)[:120]}")

        # 兜底清洗：只保留合法 product_id，防止模型引用不在候选中的商品；
        # 同时清理 summary / reason / next_question 中误写入的内部编号（F-REG-003）
        valid_ids = {product["product_id"] for product in ranked}
        result["summary"] = sanitize_visible_text(result.get("summary", ""), valid_ids)
        result["next_question"] = sanitize_visible_text(
            result.get("next_question", ""), valid_ids
        )
        result["recommendations"] = [
            {
                **item,
                "reason": sanitize_visible_text(item.get("reason", ""), valid_ids),
            }
            for item in result.get("recommendations", [])
            if isinstance(item, dict) and item.get("product_id") in valid_ids
        ]

        # findings #25：在此统一计算最终展示集——推荐卡与对比表消费同一列表，
        # 规则与 persist 一致：只展示有理由的商品，不足 3 款用总结摘录补足头部
        reasons = {
            item.get("product_id"): str(item.get("reason", "")).strip()
            for item in result["recommendations"]
        }
        display = [
            {**product, "reason": reasons[product["product_id"]]}
            for product in ranked
            if reasons.get(product["product_id"])
        ]
        if len(display) < 3:
            included = {p["product_id"] for p in display}
            fallback_reason = (result.get("summary", "") or "综合评分与销量较高，供参考。")[:80]
            for product in ranked:
                if len(display) >= 3:
                    break
                if product["product_id"] not in included:
                    display.append({**product, "reason": fallback_reason})
                    included.add(product["product_id"])

        logger.info(f"推荐生成完成：{len(result['recommendations'])} 条理由，展示集 {len(display)} 款")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"recommendation": result, "display_products": display}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
