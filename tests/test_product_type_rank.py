"""
品型约束与显式选品排序测试（N11.32 / N11.33）

- 同义词组：充电宝=移动电源，同物异名不得误判为无货
- 负向表述：没有X / 买不到X 不构成品型约束（N11.32 放宽路径）
- rank_products：品型无匹配返回空推荐并明示；显式选品对比跳过
  品型/品类/语义地板/预算/风险过滤，且保持用户选择顺序
"""

import asyncio


class _Writer:
    def __call__(self, event: dict) -> None:
        pass


class _Runtime:
    stream_writer = _Writer()


def candidate(pid, title, price, category="厨房小电器", semantic=0.9):
    return {
        "product_id": pid,
        "title": title,
        "category_name": category,
        "brand": "测试",
        "price": price,
        "promotion_price": None,
        "stock": 10,
        "sales_30d": 100,
        "rating": 4.5,
        "review_count": 10,
        "attributes": {},
        "semantic_score": semantic,
    }


# ---- 品型匹配（category_match） ----


def test_synonym_maps_to_canonical_type():
    from app.agent.shopping.category_match import match_product_type, type_in_candidate

    # 用户说"充电宝"，商品标题叫"移动电源"——同物异名，锁定同一品型
    assert match_product_type("想买个充电宝，200以内") == "移动电源"
    assert type_in_candidate("移动电源", "倍思 20000mAh 移动电源 22.5W 快充")


def test_explicit_type_locked_from_query():
    from app.agent.shopping.category_match import match_product_type

    assert match_product_type("想买一个蓝牙耳机，预算300以内，通勤使用") == "耳机"


def test_negation_releases_type_lock():
    from app.agent.shopping.category_match import match_product_type

    assert match_product_type("没有耳机的话，推荐最接近的品类") is None
    assert match_product_type("买不到耳机，看看别的") is None
    # 正常提及不受负向规则影响
    assert match_product_type("想买个耳机") == "耳机"
    assert match_product_type("没有线的那种耳机，预算300") == "耳机"


# ---- rank_products ----


def test_rank_returns_empty_when_type_has_no_stock():
    from app.agent.shopping.nodes.rank_products import rank_products

    state = {
        "query": "想买一个蓝牙耳机，预算300以内",
        "rewritten_query": "",
        "candidate_products": [
            candidate("P0001", "米家 破壁机 1.5L 大容量", 399),
            candidate("P0003", "绿联 拓展坞 9合1 Type-C", 199, category="数码配件"),
        ],
        "risk_summary": {},
        "purchase_slots": {},
    }
    result = asyncio.run(rank_products(state, _Runtime()))
    # N11.32：无货品型返回空推荐，绝不用相邻品类冒充
    assert result["ranked_products"] == []
    assert "暂无「耳机」" in result["insufficient_note"]
    assert "没有拿相近品类凑数" in result["insufficient_note"]


def test_rank_keeps_real_type_products():
    from app.agent.shopping.nodes.rank_products import rank_products

    # 品型有货（热水壶在售）时正常锁定推荐，不误伤
    state = {
        "query": "想买个电水壶，预算150以内",
        "rewritten_query": "",
        "candidate_products": [
            candidate("P0004", "小熊 恒温电热水壶 1.7L", 99),
            candidate("P0001", "米家 破壁机 1.5L", 349),
        ],
        "risk_summary": {},
        "purchase_slots": {},
    }
    result = asyncio.run(rank_products(state, _Runtime()))
    ids = [c["product_id"] for c in result["ranked_products"]]
    assert ids == ["P0004"]


def test_rank_explicit_selection_bypasses_filters():
    from app.agent.shopping.nodes.rank_products import rank_products

    # 显式选品对比：预算 200 的历史轮选中 399 元破壁机，
    # 预算/品类/语义地板/高风险过滤一律豁免，且保持用户选择顺序
    state = {
        "query": "帮我对比这 2 款商品",
        "rewritten_query": "充电宝 预算200",
        "selected_product_ids": ["P0003", "P0001"],
        "candidate_products": [
            candidate("P0001", "米家 破壁机 1.5L", 399),
            candidate("P0003", "绿联 拓展坞 9合1", 199, category="数码配件", semantic=0.2),
        ],
        "risk_summary": {"P0003": {"level": "high"}},
        "purchase_slots": {"budget_max": 200},
    }
    result = asyncio.run(rank_products(state, _Runtime()))
    ids = [c["product_id"] for c in result["ranked_products"]]
    assert ids == ["P0003", "P0001"]
