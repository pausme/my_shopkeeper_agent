"""
AI 商品决策助手（导购）LangGraph 图编排

链路：改写追问 -> 意图与槽位抽取 -> 追问决策（不足则追问并结束）->
商品召回 -> 评价与风险分析 -> 商品重排 -> 推荐生成 -> 对比表 -> 落库并输出

与问数链路（app/agent/graph.py）并存，服务不同的业务入口
"""


from langgraph.constants import END, START
from langgraph.graph import StateGraph

from app.agent.llm import llm  # noqa: F401  # 提前导入保证多供应商初始化日志只打一次
from app.agent.nodes.rewrite_question import rewrite_question
from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.nodes.analyze_reviews import analyze_reviews
from app.agent.shopping.nodes.build_comparison import build_comparison
from app.agent.shopping.nodes.decide_clarification import decide_clarification
from app.agent.shopping.nodes.emit_clarification import emit_clarification
from app.agent.shopping.nodes.extract_intent_slots import extract_intent_slots
from app.agent.shopping.nodes.generate_recommendation import generate_recommendation
from app.agent.shopping.nodes.persist_and_emit import persist_and_emit
from app.agent.shopping.nodes.rank_products import rank_products
from app.agent.shopping.nodes.recall_products import recall_products
from app.agent.shopping.state import ShoppingAgentState

builder = StateGraph(state_schema=ShoppingAgentState, context_schema=ShoppingAgentContext)

builder.add_node("rewrite_question", rewrite_question)
builder.add_node("extract_intent_slots", extract_intent_slots)
builder.add_node("decide_clarification", decide_clarification)
builder.add_node("emit_clarification", emit_clarification)
builder.add_node("recall_products", recall_products)
builder.add_node("analyze_reviews", analyze_reviews)
builder.add_node("rank_products", rank_products)
builder.add_node("generate_recommendation", generate_recommendation)
builder.add_node("build_comparison", build_comparison)
builder.add_node("persist_and_emit", persist_and_emit)

builder.add_edge(START, "rewrite_question")
builder.add_edge("rewrite_question", "extract_intent_slots")
builder.add_edge("extract_intent_slots", "decide_clarification")

# 信息不足时输出追问并结束等待用户补充；信息足够则继续推荐链路
builder.add_conditional_edges(
    source="decide_clarification",
    path=lambda state: (
        "emit_clarification" if state.get("clarification_needed") else "recall_products"
    ),
    path_map={"emit_clarification": "emit_clarification", "recall_products": "recall_products"},
)
builder.add_edge("emit_clarification", END)

builder.add_edge("recall_products", "analyze_reviews")
builder.add_edge("analyze_reviews", "rank_products")
builder.add_edge("rank_products", "generate_recommendation")
builder.add_edge("generate_recommendation", "build_comparison")
builder.add_edge("build_comparison", "persist_and_emit")
builder.add_edge("persist_and_emit", END)

shopping_graph = builder.compile()


if __name__ == "__main__":
    nodes = [n for n in shopping_graph.get_graph().nodes if not n.startswith("__")]
    print("导购图节点：", nodes)
