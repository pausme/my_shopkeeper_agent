"""
导购智能体状态（AI 商品决策助手）

ShoppingAgentState 是导购链路各节点间传递和更新的共享数据，
字段设计对齐 PRD Agent 改造方案第 7 节
"""

from typing import TypedDict


class ShoppingAgentState(TypedDict):
    """一次导购链路中的核心状态"""

    query: str  # 用户原始输入
    rewritten_query: str  # 结合历史改写后的独立需求
    history: list[dict]  # 最近对话 [{role, content}]
    session_id: str  # 导购会话 ID
    user_id: str | None  # 登录用户 ID（可为空）

    intent: str  # 意图：recommendation / comparison / summary / followup
    purchase_slots: dict  # 槽位：category/scene/budget_min/budget_max/audience/preferences/exclusions
    selected_product_ids: list[str]  # 用户指定要比较的商品

    clarification_needed: bool  # 是否需要追问
    clarification_question: str  # 追问内容
    clarification_count: int  # 本会话已追问次数（防超限）

    candidate_products: list[dict]  # 召回候选（payload + semantic_score）
    review_summary: dict  # 商品 -> 评价要点 {product_id: {negative_tags, positive_tags, sample_size}}
    risk_summary: dict  # 商品 -> 风险摘要 {product_id: {level, summary, suitable, not_suitable}}
    ranked_products: list[dict]  # 重排后的商品（含 match_score 与最终得分）

    recommendation: dict  # 推荐结果 {summary, recommendations:[{product_id, reason}], next_question}
    comparison_table: dict  # 对比表 {headers, rows}

    error: str | None  # 错误信息


def format_history(history: list[dict] | None, max_messages: int = 6) -> str:
    """把最近对话渲染成提示词可读的文本，超出的旧消息截断

    返回空字符串表示没有历史（独立问题），调用方在提示词里以"无"占位。
    """

    if not history:
        return ""

    role_names = {"user": "用户", "assistant": "助手"}
    lines = []
    for message in history[-max_messages:]:
        role = role_names.get(message.get("role", ""), None)
        content = str(message.get("content", "")).strip()
        if role and content:
            lines.append(f"{role}：{content}")
    return "\n".join(lines)
