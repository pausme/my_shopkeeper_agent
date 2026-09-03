"""
推荐生成节点（导购链路）

一次 LLM 调用生成整体结论与逐商品推荐理由；
理由强制锚定给定事实字段（价格/评分/销量/评价/风险），禁止编造（M8 幻觉兜底）
"""

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from yaml import dump as yaml_dump

from app.agent.llm import llm
from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


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

        # 兜底清洗：只保留合法 product_id，防止模型引用不在候选中的商品
        valid_ids = {product["product_id"] for product in ranked}
        result["recommendations"] = [
            item
            for item in result.get("recommendations", [])
            if isinstance(item, dict) and item.get("product_id") in valid_ids
        ]

        logger.info(f"推荐生成完成：{len(result['recommendations'])} 条理由")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"recommendation": result}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
