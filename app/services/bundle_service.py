"""
搭配购买服务（二期 P1 / PRD 3.4）

规则版（无 LLM 依赖，确定性输出）：
- 组合购：品型互补表（空气炸锅→破壁机/电煮锅 等场景组合）
- 补充购：同品类不同品型
- 替代购：同品类价格带相近（±30%）的其他商品
全部结果经风险过滤（中高风险不进搭配）。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import ProductInfoMySQL, ProductRiskSummaryMySQL

# 品型互补表：主商品品型 -> 推荐搭配的品型（跨品类组合购）
BUNDLE_RULES: dict[str, list[str]] = {
    "空气炸锅": ["破壁机", "电煮锅", "豆浆机"],
    "破壁机": ["豆浆机", "电煮锅"],
    "豆浆机": ["破壁机", "热水壶"],
    "电煮锅": ["空气炸锅", "热水壶"],
    "热水壶": ["电煮锅", "豆浆机"],
    "饮水机": ["压缩袋", "置物架"],
    "落地灯": ["四件套", "枕头"],
    "四件套": ["枕头", "落地灯"],
    "枕头": ["四件套", "按摩仪"],
    "按摩仪": ["枕头", "四件套"],
    "压缩袋": ["推车", "置物架"],
    "推车": ["压缩袋", "置物架"],
    "充电器": ["充电宝", "拓展坞"],
    "充电宝": ["充电器", "拓展坞"],
    "拓展坞": ["鼠标", "硬盘"],
    "手环": ["充电器", "充电宝"],
    "鼠标": ["键盘", "硬盘"],
    "硬盘": ["鼠标", "拓展坞"],
    "辅食机": ["奶瓶", "奶嘴"],
    "安全座椅": ["推车", "浴巾"],
    "奶瓶": ["奶嘴", "辅食机"],
    "奶嘴": ["奶瓶", "浴巾"],
    "床中床": ["浴巾", "枕头"],
}


def to_card(row: ProductInfoMySQL, reason: str = "") -> dict:
    """ORM 行 -> 前端商品卡结构"""

    return {
        "product_id": row.product_id,
        "title": row.title,
        "category_name": row.category_name,
        "brand": row.brand,
        "price": float(row.price),
        "promotion_price": float(row.promotion_price) if row.promotion_price else None,
        "rating": float(row.rating),
        "sales_30d": row.sales_30d,
        "reason": reason,
    }


class BundleService:
    """搭配购买建议（组合购/补充购/替代购）"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def recommend(
        self,
        product_id: str,
        user_preferences: list[dict] | None = None,
    ) -> dict | None:
        """输出主商品的搭配方案；商品不存在返回 None"""

        result = await self.session.execute(
            select(ProductInfoMySQL).where(ProductInfoMySQL.product_id == product_id)
        )
        main_row = result.scalars().first()
        if main_row is None or main_row.is_deleted:
            return None

        title = main_row.title or ""
        main_type = next((kw for kw in BUNDLE_RULES if kw in title), None)
        main_category = main_row.category_name
        main_price = float(main_row.promotion_price or main_row.price)

        # 候选池：全部在售商品（排除主商品与中高风险）
        pool_result = await self.session.execute(
            select(ProductInfoMySQL).where(
                ProductInfoMySQL.is_deleted == 0,
                ProductInfoMySQL.status == "on_sale",
                ProductInfoMySQL.product_id != product_id,
            )
        )
        pool = list(pool_result.scalars().all())
        risk_result = await self.session.execute(
            select(ProductRiskSummaryMySQL).where(
                ProductRiskSummaryMySQL.risk_level.in_(["medium", "high"])
            )
        )
        risky_ids = {row.product_id for row in risk_result.scalars()}
        pool = [p for p in pool if p.product_id not in risky_ids]

        def card(row: ProductInfoMySQL, reason: str) -> dict:
            return to_card(row, reason)

        bundles: list[dict] = []
        listed: set[str] = set()

        # 1. 组合购：标题命中互补品型的同品类商品
        if main_type:
            combo_types = BUNDLE_RULES.get(main_type, [])
            combo = [
                p for p in pool
                if p.category_name == main_category
                and any(t in p.title for t in combo_types)
            ]
            combo.sort(key=lambda p: float(p.promotion_price or p.price))
            if combo:
                picked = combo[:3]
                bundles.append({
                    "type": "组合购",
                    "reason": f"与「{main_type}」搭配使用的{main_category}场景常见组合",
                    "products": [
                        card(p, f"与「{main_type}」形成场景互补，到手价 ¥{float(p.promotion_price or p.price)}")
                        for p in picked
                    ],
                })
                listed |= {p.product_id for p in picked}

        # 2. 补充购：同品类评分较高且未列出
        supplement = [p for p in pool if p.category_name == main_category and p.product_id not in listed]
        supplement.sort(key=lambda p: float(p.rating), reverse=True)
        if supplement:
            picked = supplement[:2]
            bundles.append({
                "type": "补充购",
                "reason": f"{main_category}内评分较高的其他选择，可按需补充",
                "products": [
                    card(p, f"{p.category_name}场景补充，评分 {float(p.rating):.1f}、月销 {p.sales_30d}")
                    for p in picked
                ],
            })
            listed |= {p.product_id for p in picked}

        # 3. 替代购：同品类价格带相近（±30%）未列出
        alternatives = [
            p for p in pool
            if p.category_name == main_category
            and p.product_id not in listed
            and abs(float(p.promotion_price or p.price) - main_price) / max(main_price, 1) <= 0.3
        ]
        alternatives.sort(key=lambda p: float(p.rating), reverse=True)
        if alternatives:
            picked = alternatives[:2]
            bundles.append({
                "type": "替代购",
                "reason": "价格与主商品相近的可替代选择",
                "products": [
                    card(p, f"价格与主商品相近（¥{float(p.promotion_price or p.price)}），评分可比")
                    for p in picked
                ],
            })

        return {"main": to_card(main_row), "bundles": bundles}
