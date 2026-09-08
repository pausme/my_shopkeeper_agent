"""
购物车模拟规则引擎测试（二期 P2）

纯函数测试：满减阈值、优惠券叠加、应付下限与数量合计。
规则取自 conf/cart_rules.yaml（厨房小电器满500减50 等）。
"""

from app.services.cart_service import simulate


def item(title: str, price: float, category: str, quantity: int = 1) -> dict:
    return {"title": title, "price": price, "quantity": quantity, "category_name": category}


def test_subtotal_without_any_discount():
    result = simulate([item("枕头", 199, "家居生活")])
    assert result["subtotal"] == 199
    assert result["discounts"] == []
    assert result["payable"] == 199


def test_category_threshold_hit_and_miss():
    # 厨房小电器 560 >= 500 命中满 500 减 50
    hit = simulate([item("空气炸锅", 560, "厨房小电器")])
    assert any("满减" in d["type"] for d in hit["discounts"])
    assert hit["total_discount"] == 50
    assert hit["payable"] == 510

    # 460 未达阈值
    miss = simulate([item("煮蛋器", 460, "厨房小电器")])
    assert miss["discounts"] == []
    assert miss["payable"] == 460


def test_category_subtotal_counts_quantity_per_category():
    # 同品类两件合计 300 命中家居生活满 300 减 30；他品类不参与
    result = simulate([
        item("落地灯", 180, "家居生活"),
        item("收纳盒", 120, "家居生活", quantity=1),
        item("充电宝", 100, "数码配件"),
    ])
    assert result["total_discount"] == 30
    assert result["payable"] == 370


def test_fixed_coupon_and_threshold_stack():
    result = simulate(
        [item("空气炸锅", 560, "厨房小电器")],
        coupon_code="NEW50",
    )
    # 满减 50 + 立减 50
    assert result["total_discount"] == 100
    assert result["payable"] == 460


def test_percentage_coupon_rounded():
    result = simulate([item("充电宝", 199, "数码配件")], coupon_code="PICK90")
    # 9 折省 19.9
    assert result["total_discount"] == 19.9
    assert result["payable"] == 179.1


def test_coupon_cannot_make_payable_negative():
    result = simulate([item("手机支架", 39, "数码配件")], coupon_code="NEW50")
    assert result["payable"] == 0
    # 优惠券折扣被钳制到 39，不出现负应付
    assert result["total_discount"] == 39


def test_unknown_coupon_ignored():
    result = simulate([item("奶瓶", 120, "母婴用品")], coupon_code="NO_SUCH_CODE")
    assert result["discounts"] == []
    assert result["payable"] == 120


def test_items_count_sums_quantities():
    result = simulate([
        item("奶瓶", 120, "母婴用品", quantity=2),
        item("辅食机", 300, "厨房小电器", quantity=3),
    ])
    assert result["items_count"] == 5
    assert result["subtotal"] == 1140
