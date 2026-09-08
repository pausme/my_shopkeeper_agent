"""
购物车模拟与优惠券规则引擎（二期 P2，PRD 3.4 / S3-3）

优惠券规则配置化（conf/cart_rules.yaml）：
- 满减：满 threshold 减 discount
- 折扣：percentage 折（如 90 = 9 折）
- 组合折扣：同时购买指定品型组合时的额外优惠

模拟逻辑：组合价 → 品类满减 → 券叠加，输出明细与省额。
"""

from pathlib import Path

import yaml

RULES_PATH = Path(__file__).parents[2] / "conf" / "cart_rules.yaml"


def load_rules() -> dict:
    """加载优惠券/满减规则；配置缺失时返回空规则集"""

    if not RULES_PATH.exists():
        return {"coupons": [], "category_thresholds": []}
    return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}


def simulate(
    items: list[dict],
    coupon_code: str | None = None,
) -> dict:
    """计算购物车组合价格与优惠效果

    items: [{title, price, quantity, category_name}]
    返回：原价合计、优惠明细、应付合计、命中的规则说明
    """

    rules = load_rules()
    subtotal = sum(float(item["price"]) * int(item.get("quantity", 1)) for item in items)

    applied: list[dict] = []
    total_discount = 0.0

    # 1. 品类满减：每个品类小计独立判断阈值
    for rule in rules.get("category_thresholds", []):
        category = rule.get("category", "")
        threshold = float(rule.get("threshold", 0))
        discount = float(rule.get("discount", 0))
        if not category or discount <= 0:
            continue
        category_subtotal = sum(
            float(i["price"]) * int(i.get("quantity", 1))
            for i in items
            if i.get("category_name") == category
        )
        if category_subtotal >= threshold:
            applied.append({
                "type": "满减",
                "desc": f"{category}满{threshold}减{discount}",
                "discount": discount,
            })
            total_discount += discount

    # 2. 优惠券：按 code 匹配
    coupon = next(
        (c for c in rules.get("coupons", []) if c.get("code") == coupon_code),
        None,
    )
    if coupon:
        code_discount = 0.0
        if coupon.get("type") == "percentage":
            rate = 1 - float(coupon.get("value", 100)) / 100
            code_discount = round(subtotal * rate, 2)
            desc = f"{coupon['code']}：{coupon['value']}折"
        else:  # fixed
            code_discount = float(coupon.get("value", 0))
            desc = f"{coupon['code']}：立减 {code_discount} 元"
        code_discount = min(code_discount, subtotal - total_discount)
        if code_discount > 0:
            applied.append({"type": "优惠券", "desc": desc, "discount": code_discount})
            total_discount += code_discount

    payable = max(round(subtotal - total_discount, 2), 0.0)

    return {
        "items_count": sum(int(i.get("quantity", 1)) for i in items),
        "subtotal": round(subtotal, 2),
        "discounts": applied,
        "total_discount": round(total_discount, 2),
        "payable": payable,
    }
