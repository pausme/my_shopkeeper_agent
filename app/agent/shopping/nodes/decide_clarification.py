"""
追问决策节点（导购链路）

规则判断（不调 LLM），对齐 PRD 10.2：
- 最多连续追问 2 次，每次只问 1 个最关键问题
- 第一问：品类缺失 → 品类四选一
- 第二问：品类已知 → 该品类的关键参数/偏好题（题库维护）
- 每问都带快捷选项（含"跳过"），用户跳过或回答"不知道"时由默认假设兜底
- 已有多轮历史（追问后半程）不再追问，避免用户流失
"""

from langgraph.runtime import Runtime

from app.agent.shopping.context import ShoppingAgentContext
from app.agent.shopping.state import ShoppingAgentState
from app.core.log import logger

# PRD 10.2：最多连续追问 2 次
MAX_CLARIFICATION = 2

CATEGORY_QUESTION = "想先确认一下：您想看哪个品类的商品？"
CATEGORY_OPTIONS = ["厨房小电器", "家居生活", "数码配件", "母婴用品", "跳过"]

# 品类关键参数题库（PRD 10.2：品类存在强关键参数但用户未提供时追问）
CATEGORY_PARAM_BANK: dict[str, tuple[str, list[str]]] = {
    "厨房小电器": ("厨房电器的使用上，您更看重哪一点？", ["好清洗", "功能全面", "静音", "小巧不占地方", "跳过"]),
    "家居生活": ("家居选品上您更偏好哪个方向？", ["收纳实用", "舒适体验", "颜值装饰", "跳过"]),
    "数码配件": ("数码配件主要搭配什么设备使用？", ["手机", "电脑", "平板", "通用", "跳过"]),
    "母婴用品": ("宝宝多大月龄？", ["0-1 岁", "1-3 岁", "3 岁以上", "不确定", "跳过"]),
}

# 追问的回答会进入偏好槽位，跳过类回答不进入
SKIP_ANSWERS = {"跳过", "不确定", "不知道"}


async def decide_clarification(
    state: ShoppingAgentState, runtime: Runtime[ShoppingAgentContext]
):
    """判断是否需要向用户追问关键缺失信息"""

    writer = runtime.stream_writer
    step = "判断是否追问"
    writer({"type": "progress", "step": step, "status": "running"})

    slots = state.get("purchase_slots") or {}
    has_history = bool(state.get("history"))
    asked = state.get("clarification_count", 0)
    category = slots.get("category")

    question = None
    options: list[str] = []
    # 品类缺失即追问（PRD 10.1：无法识别品类时友好提示而非强行推荐）。
    # 不依赖 LLM 意图判定——首轮（无历史）品类缺失就必须补问；
    # 有显式商品 ID（用户指定对比对象）则无需品类；追问后半程不再追问
    if (
        asked < MAX_CLARIFICATION
        and not has_history
        and not slots.get("product_ids")
    ):
        if not category:
            question = CATEGORY_QUESTION
            options = CATEGORY_OPTIONS
        elif not slots.get("preferences"):
            bank_question, bank_options = CATEGORY_PARAM_BANK.get(category, (None, []))
            if bank_question:
                question = bank_question
                options = bank_options

    logger.info(f"追问决策：{'需要' if question else '不需要'}追问")
    writer({"type": "progress", "step": step, "status": "success"})
    return {
        "clarification_needed": question is not None,
        "clarification_question": question or "",
        "clarification_options": options,
    }
