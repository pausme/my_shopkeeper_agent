"""
品类程序化匹配（防 LLM 抖动的安全网）

意图抽取是单点故障：LLM 偶发漏抽品类会导致品类硬过滤失效、跨品类推荐。
这里用关键词映射提供确定性兜底，优先级低于 LLM 槽位
"""

import re

from app.core.log import logger

# 品类关键词映射：商品词与场景词 → 标准品类
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "厨房小电器": [
        "空气炸锅", "破壁机", "豆浆机", "电煮锅", "热水壶", "饮水机", "电饭煲",
        "咖啡机", "厨房", "烹饪", "做饭",
    ],
    "家居生活": [
        "落地灯", "四件套", "枕头", "按摩仪", "压缩袋", "置物架", "收纳",
        "人体工学椅", "床垫", "除湿机", "家居", "搬家", "租房好物",
    ],
    "数码配件": [
        "充电器", "拓展坞", "充电宝", "手环", "鼠标", "硬盘", "耳机",
        "键盘", "显示器", "数码", "手机配件",
    ],
    "母婴用品": [
        "辅食机", "安全座椅", "浴巾", "奶瓶", "床中床", "奶嘴", "婴儿推车",
        "宝宝", "婴儿", "母婴", "幼儿", "产妇",
    ],
}


def guess_category(*texts) -> str | None:
    """从若干段文本中按关键词猜测品类，命中返回标准品类名，否则 None"""

    joined = " ".join(str(t) for t in texts if t)
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in joined:
                logger.info(f"品类关键词兜底命中：{keyword} -> {category}")
                return category
    return None


# 品型同义词组（findings #24 / N11.32）：
# - 查询侧：组内任一词命中即锁定该规范品型（用户说"充电宝"=商品标题"移动电源"）
# - 候选侧：标题/属性命中组内任一词才算该品型——同物异名不得误判为无货
PRODUCT_TYPE_SYNONYMS: list[tuple[str, list[str]]] = [
    ("空气炸锅", ["空气炸锅"]),
    ("破壁机", ["破壁机"]),
    ("豆浆机", ["豆浆机"]),
    ("电煮锅", ["电煮锅"]),
    ("热水壶", ["热水壶", "电水壶", "开水壶"]),
    ("饮水机", ["饮水机"]),
    ("电饭煲", ["电饭煲", "电饭锅"]),
    ("咖啡机", ["咖啡机"]),
    ("落地灯", ["落地灯"]),
    ("四件套", ["四件套"]),
    ("枕头", ["枕头", "枕芯"]),
    ("按摩仪", ["按摩仪", "按摩器"]),
    ("压缩袋", ["压缩袋"]),
    ("置物架", ["置物架", "收纳架", "小推车"]),
    ("床垫", ["床垫"]),
    ("除湿机", ["除湿机"]),
    ("移动电源", ["移动电源", "充电宝"]),
    ("充电器", ["充电器", "充电头"]),
    ("拓展坞", ["拓展坞", "扩展坞"]),
    ("手环", ["手环"]),
    ("鼠标", ["鼠标"]),
    ("硬盘", ["硬盘"]),
    ("耳机", ["耳机", "耳麦"]),
    ("键盘", ["键盘"]),
    ("显示器", ["显示器", "显示屏"]),
    ("辅食机", ["辅食机"]),
    ("安全座椅", ["安全座椅"]),
    ("浴巾", ["浴巾"]),
    ("奶瓶", ["奶瓶"]),
    ("床中床", ["床中床"]),
    ("奶嘴", ["奶嘴"]),
    ("婴儿推车", ["婴儿推车", "婴儿车"]),
]

# 品型词前紧邻这些表述时视为放宽（N11.32："没有耳机的话推荐最接近的"），不构成约束
_NEGATION_BEFORE = re.compile(r"(没有|无|买不到|买不着|不是)$")


def _earliest_hit(joined: str, words: list[str]) -> tuple[str, int] | None:
    """返回组内最早出现的词与其位置，未命中返回 None"""

    best: tuple[str, int] | None = None
    for word in words:
        index = joined.find(word)
        if index != -1 and (best is None or index < best[1]):
            best = (word, index)
    return best


def match_product_type(*texts) -> str | None:
    """从文本中命中具体品型（含同义词组），返回规范品型名（如"移动电源"）或 None"""

    joined = " ".join(str(t) for t in texts if t)
    for canonical, words in PRODUCT_TYPE_SYNONYMS:
        hit = _earliest_hit(joined, words)
        if hit is None:
            continue
        word, index = hit
        prefix = joined[max(0, index - 4) : index]
        if _NEGATION_BEFORE.search(prefix):
            continue
        logger.info(f"品型锁定：{word} -> {canonical}")
        return canonical
    return None


def type_in_candidate(type_name: str, *texts) -> bool:
    """候选商品的标题/属性文本是否属于该品型（组内同义词任一命中）"""

    words = dict(PRODUCT_TYPE_SYNONYMS).get(type_name, [type_name])
    joined = " ".join(str(t) for t in texts if t)
    return any(word in joined for word in words)
