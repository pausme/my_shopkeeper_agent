"""
品类程序化匹配（防 LLM 抖动的安全网）

意图抽取是单点故障：LLM 偶发漏抽品类会导致品类硬过滤失效、跨品类推荐。
这里用关键词映射提供确定性兜底，优先级低于 LLM 槽位
"""

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
