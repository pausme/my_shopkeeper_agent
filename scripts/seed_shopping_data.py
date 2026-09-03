"""
导购种子数据构建脚本

生成 4 个首期品类（厨房小电器/家居生活/数码配件/母婴用品）各 6 款商品、
每款 25 条模板化评价，并从评价聚合出风险摘要，随后：
  1. 商品/评价/风险摘要落入 meta 库（覆盖式重建）
  2. 商品语义向量重建入 Qdrant product_info_collection
  3. 评价全文重建入 ES review_index

用法：uv run python scripts/seed_shopping_data.py
"""

import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.models.product import (
    ProductInfoMySQL,
    ProductReviewMySQL,
    ProductRiskSummaryMySQL,
)
from app.repositories.es.review_es_repository import ReviewESRepository
from app.repositories.mysql.meta.product_repository import ProductRepository
from app.repositories.qdrant.product_qdrant_repository import ProductQdrantRepository

random.seed(42)

# ---------- 商品定义：品类 -> (标题, 品牌, 原价, 到手价, 属性, 卖点) ----------

PRODUCTS: dict[str, list[dict]] = {
    "厨房小电器": [
        {"title": "米家 破壁机 1.5L 大容量 低音降噪", "brand": "米家", "price": 399, "promo": 349,
         "attrs": {"容量": "1.5L", "功率": "800W", "噪音": "约60dB", "功能": "破壁/豆浆/辅食"}},
        {"title": "九阳 豆浆机迷你 0.35L 一人食免滤", "brand": "九阳", "price": 199, "promo": 159,
         "attrs": {"容量": "0.35L", "功率": "600W", "噪音": "约70dB", "功能": "豆浆/米糊"}},
        {"title": "苏泊尔 电煮锅 1.8L 多功能一体锅", "brand": "苏泊尔", "price": 149, "promo": 129,
         "attrs": {"容量": "1.8L", "功率": "700W", "内胆": "不粘涂层", "功能": "煮/煎/火锅"}},
        {"title": "小熊 恒温电热水壶 1.7L 12段控温", "brand": "小熊", "price": 129, "promo": 99,
         "attrs": {"容量": "1.7L", "控温": "40-90℃ 12段", "材质": "316不锈钢", "功能": "恒温/除氯"}},
        {"title": "摩飞 空气炸锅 5.5L 可视大容量", "brand": "摩飞", "price": 599, "promo": 499,
         "attrs": {"容量": "5.5L", "功率": "1700W", "噪音": "约65dB", "功能": "炸/烤/复热"}},
        {"title": "北鼎 饮水机即热式 台式 mini", "brand": "北鼎", "price": 1099, "promo": 999,
         "attrs": {"出水": "3秒即热", "控温": "8段", "水箱": "2L", "噪音": "静音"}},
    ],
    "家居生活": [
        {"title": "网易严选 落地灯 北欧简约 卧室客厅", "brand": "网易严选", "price": 299, "promo": 249,
         "attrs": {"高度": "1.6m", "光源": "LED 三色", "材质": "实木+布艺", "风格": "北欧"}},
        {"title": "水星家纺 全棉四件套 100支贡缎", "brand": "水星家纺", "price": 399, "promo": 329,
         "attrs": {"支数": "100S", "材质": "新疆长绒棉", "床型": "1.5/1.8m", "工艺": "贡缎"}},
        {"title": "京东京造 记忆棉枕头 护颈椎助睡眠", "brand": "京东京造", "price": 169, "promo": 139,
         "attrs": {"材质": "记忆棉", "高度": "8/10cm 可选", "适用": "颈椎不适人群"}},
        {"title": "象术 颈部按摩仪 揉捏热敷", "brand": "象术", "price": 459, "promo": 399,
         "attrs": {"模式": "揉捏/热敷", "续航": "约2周", "重量": "1.2kg"}},
        {"title": "太力 真空压缩袋 11件套 棉被收纳", "brand": "太力", "price": 79, "promo": 59,
         "attrs": {"数量": "11件", "材质": "PA+PE 加厚", "配件": "电泵+手泵"}},
        {"title": "得力 移动小推车置物架 三层", "brand": "得力", "price": 119, "promo": 89,
         "attrs": {"层数": "3层", "材质": "碳钢喷塑", "承重": "每层10kg", "带轮": "是"}},
    ],
    "数码配件": [
        {"title": "Anker 安克 65W 氮化镓充电器 三口", "brand": "安克", "price": 199, "promo": 169,
         "attrs": {"功率": "65W", "接口": "2C+1A", "协议": "PD/QC", "体积": "mini"}},
        {"title": "绿联 拓展坞 9合1 Type-C", "brand": "绿联", "price": 249, "promo": 199,
         "attrs": {"接口": "HDMI/网口/SD/3×USB", "供电": "100W PD 透传", "线长": "15cm"}},
        {"title": "倍思 20000mAh 移动电源 22.5W 快充", "brand": "倍思", "price": 149, "promo": 119,
         "attrs": {"容量": "20000mAh", "功率": "22.5W", "显示": "电量数显", "重量": "约430g"}},
        {"title": "小米 手环9 NFC版 血氧睡眠监测", "brand": "小米", "price": 269, "promo": 249,
         "attrs": {"屏幕": "1.62\" AMOLED", "续航": "约16天", "监测": "心率/血氧/睡眠", "防水": "5ATM"}},
        {"title": "罗技 MX Anywhere 3S 无线鼠标", "brand": "罗技", "price": 599, "promo": 549,
         "attrs": {"连接": "蓝牙/接收器双模", "传感器": "8000DPI 玻璃面可用", "续航": "约70天"}},
        {"title": "闪迪 1TB Type-C 移动固态硬盘", "brand": "闪迪", "price": 799, "promo": 699,
         "attrs": {"容量": "1TB", "速度": "1050MB/s", "接口": "Type-C", "三防": "抗震"}},
    ],
    "母婴用品": [
        {"title": "babycare 婴儿辅食机 蒸煮搅一体", "brand": "babycare", "price": 399, "promo": 349,
         "attrs": {"容量": "0.4L", "功能": "蒸/煮/搅", "材质": "食品级PP", "噪音": "低噪"}},
        {"title": "好孩子 儿童安全座椅 0-7岁 360°旋转", "brand": "好孩子", "price": 1699, "promo": 1499,
         "attrs": {"适用": "0-7岁", "安装": "ISOFIX", "旋转": "360°", "认证": "3C/ECE"}},
        {"title": "全棉时代 婴儿纯棉纱布浴巾 6层", "brand": "全棉时代", "price": 99, "promo": 79,
         "attrs": {"尺寸": "95×95cm", "层数": "6层纱布", "材质": "100%棉", "认证": "A类"}},
        {"title": "贝亲 宽口径玻璃奶瓶 160ml", "brand": "贝亲", "price": 89, "promo": 75,
         "attrs": {"材质": "硼硅酸玻璃", "口径": "宽口", "奶嘴": "SS号 仿母乳"}},
        {"title": "可优比 婴儿床中床 便携仿生睡床", "brand": "可优比", "price": 299, "promo": 259,
         "attrs": {"适用": "0-12个月", "材质": "棉+蜂窝网", "特点": "防惊跳 便携"}},
        {"title": "世喜 安抚奶嘴超软硅胶 0-6个月", "brand": "世喜", "price": 59, "promo": 49,
         "attrs": {"材质": "食品级硅胶", "月龄": "0-6个月", "特点": "仿乳房触感"}},
    ],
}

# ---------- 评价模板池 ----------

POSITIVE_TEMPLATES = [
    "收到就用了一次，{good_point}，整体很满意，推荐。",
    "质量比想象中好，{good_point}，物流也快。",
    "用了一周来评价：{good_point}，值这个价。",
    "第二次回购了，{good_point}，家人都说好。",
    "包装很好，{good_point}，客服态度也不错。",
    "给爸妈买的，{good_point}，他们很喜欢。",
    "对比了好几家最后选这个，{good_point}，没踩坑。",
    "外观漂亮，{good_point}，做工细致。",
]

GOOD_POINTS = [
    "操作简单上手快", "做工扎实没有毛刺", "噪音控制得不错", "续航/功率够用",
    "手感舒服质感好", "清洁起来很方便", "体积小巧不占地方", "细节设计很贴心",
]

NEUTRAL_TEMPLATES = [
    "整体中规中矩，{neutral_point}，符合这个价位的预期。",
    "还行吧，{neutral_point}，没有惊喜也没有失望。",
    "功能够用，{neutral_point}，外观一般。",
]

NEUTRAL_POINTS = [
    "部分功能用不上", "说明书写得不细", "配件有点少", "颜色和图片有色差",
]

NEGATIVE_POOL: list[tuple[str, str]] = [
    ("噪音明显偏大，晚上用影响休息", "噪音大"),
    ("用了两周出现了异响，质量堪忧", "质量差"),
    ("发热比较严重，长时间用不敢放手边", "发热"),
    ("有塑料味/异味，散了很久才好", "有异味"),
    ("实际容量/尺寸比想象小，有点虚标", "容量虚标"),
    ("做工一般，接缝处有毛边", "做工差"),
    ("物流慢，等了一个多星期", "物流慢"),
    ("售后响应慢，问题迟迟不解决", "售后差"),
    ("用了一个月就坏了，已经申请售后", "易损坏"),
    ("和描述不符，功能与宣传有差距", "与描述不符"),
]

# 品类相关的适合/不适合话术
SUITABLE_HINTS: dict[str, tuple[str, str]] = {
    "厨房小电器": ("租房族、小家庭日常烹饪、辅食制作", "对静音要求极高的开放式厨房、追求专业级出品"),
    "家居生活": ("新家布置、租房改善、提升睡眠质量", "追求进口大牌质感、对材质有极致要求"),
    "数码配件": ("通勤办公、差旅出行、多设备用户", "重度游戏玩家、需要极端性能的场景"),
    "母婴用品": ("新生儿家庭、送礼探望产妇", "对材质认证有特殊严苛要求的家庭（建议线下核实）"),
}


def build_products() -> list[ProductInfoMySQL]:
    """把商品定义展开成 ORM 对象，销量评分与差评率强相关，保证数据自洽"""

    products: list[ProductInfoMySQL] = []
    for category_name, items in PRODUCTS.items():
        for index, item in enumerate(items):
            # 差评率：同品类内从 4% 到 24% 线性分布，驱动评分与风险差异
            negative_ratio = 0.04 + 0.2 * (index / (len(items) - 1))
            rating = round(4.9 - negative_ratio * 2.2, 2)
            sales = int(3000 - negative_ratio * 9000 + random.randint(-400, 400))
            review_count = 200 + int(negative_ratio * 4000) + random.randint(-50, 50)
            products.append(
                ProductInfoMySQL(
                    product_id=f"P{len(products) + 1:04d}",
                    title=item["title"],
                    category_id=f"C{list(PRODUCTS).index(category_name) + 1:02d}",
                    category_name=category_name,
                    brand=item["brand"],
                    price=item["price"],
                    promotion_price=item["promo"],
                    stock=random.randint(50, 900),
                    sales_30d=max(sales, 100),
                    rating=rating,
                    review_count=review_count,
                    status="on_sale",
                    attributes_json=item["attrs"],
                    detail_text=item["title"] + "；" + "；".join(
                        f"{k}：{v}" for k, v in item["attrs"].items()
                    ),
                    is_deleted=0,
                )
            )
    return products


def build_reviews(products: list[ProductInfoMySQL]) -> list[ProductReviewMySQL]:
    """按商品的差评率参数生成评价：情感分布、标签、时间近 90 天内递减"""

    reviews: list[ProductReviewMySQL] = []
    now = datetime.now()
    for product in products:
        negative_ratio = round((4.9 - float(product.rating)) / 2.2, 3)
        n_negative = max(1, round(25 * negative_ratio))
        n_neutral = random.randint(2, 4)
        n_positive = 25 - n_negative - n_neutral
        sentiments = (
            [("positive", None)] * n_positive
            + [("neutral", None)] * n_neutral
            + [("negative", None)] * n_negative
        )
        random.shuffle(sentiments)

        for order, (sentiment, _) in enumerate(sentiments):
            created = now - timedelta(days=random.randint(1, 90))
            if sentiment == "positive":
                content = random.choice(POSITIVE_TEMPLATES).format(
                    good_point=random.choice(GOOD_POINTS)
                )
                tags = [random.choice(["质量好", "性价比高", "外观漂亮", "物流快", "操作方便"])]
            elif sentiment == "neutral":
                content = random.choice(NEUTRAL_TEMPLATES).format(
                    neutral_point=random.choice(NEUTRAL_POINTS)
                )
                tags = ["中规中矩"]
            else:
                content, tag = random.choice(NEGATIVE_POOL)
                tags = [tag]
            reviews.append(
                ProductReviewMySQL(
                    review_id=f"R{uuid.uuid4().hex[:12].upper()}",
                    product_id=product.product_id,
                    rating={"positive": 5, "neutral": 3, "negative": random.choice([1, 2])}[sentiment],
                    content=content,
                    sku_text="默认规格",
                    sentiment=sentiment,
                    review_tags_json=tags,
                    created_at=created,
                    is_deleted=0,
                )
            )
    return reviews


def build_risk_summaries(
    products: list[ProductInfoMySQL], reviews: list[ProductReviewMySQL]
) -> list[ProductRiskSummaryMySQL]:
    """从评价聚合风险摘要：差评占比定级，标签归纳摘要，话术来自品类模板"""

    by_product: dict[str, list[ProductReviewMySQL]] = {}
    for review in reviews:
        by_product.setdefault(review.product_id, []).append(review)

    summaries = []
    for product in products:
        product_reviews = by_product[product.product_id]
        negative = [r for r in product_reviews if r.sentiment == "negative"]
        negative_tags = [t for r in negative for t in (r.review_tags_json or [])]
        ratio = len(negative) / len(product_reviews)
        level = "low" if ratio < 0.12 else ("medium" if ratio < 0.2 else "high")

        suitable, not_suitable = SUITABLE_HINTS[product.category_name]
        if negative_tags:
            top_tags = sorted(set(negative_tags), key=negative_tags.count, reverse=True)[:3]
            risk_summary = (
                f"差评占比约 {ratio:.0%}（样本 {len(product_reviews)} 条），"
                f"主要反馈集中在：{'、'.join(top_tags)}。"
            )
            if "噪音大" in top_tags:
                not_suitable += "；对噪音敏感人群需谨慎"
            if "质量差" in top_tags or "易损坏" in top_tags:
                not_suitable += "；注重耐用性的用户建议考虑更高价位型号"
        else:
            risk_summary = f"差评占比约 {ratio:.0%}（样本 {len(product_reviews)} 条），未发现集中性风险反馈。"

        positive_tags = [
            t for r in product_reviews if r.sentiment == "positive"
            for t in (r.review_tags_json or [])
        ]
        positive_summary = (
            "好评关键词：" + "、".join(sorted(set(positive_tags))[:4])
            if positive_tags else "暂无集中好评关键词"
        )
        summaries.append(
            ProductRiskSummaryMySQL(
                product_id=product.product_id,
                risk_level=level,
                risk_tags_json=sorted(set(negative_tags)),
                risk_summary=risk_summary,
                positive_summary=positive_summary,
                suitable_for=suitable,
                not_suitable_for=not_suitable,
                sample_size=len(product_reviews),
                is_deleted=0,
            )
        )
    return summaries


def product_embedding_text(product: ProductInfoMySQL) -> str:
    """商品向量化文本：标题 + 类目 + 品牌 + 属性键值，建立多维语义入口"""

    attrs = product.attributes_json or {}
    attr_text = " ".join(f"{k}：{v}" for k, v in attrs.items())
    return f"{product.title} {product.category_name} {product.brand or ''} {attr_text}"


async def main():
    products = build_products()
    reviews = build_reviews(products)
    summaries = build_risk_summaries(products, reviews)
    print(f"生成：商品 {len(products)}，评价 {len(reviews)}，风险摘要 {len(summaries)}")

    # 初始化客户端
    meta_mysql_client_manager.init()
    qdrant_client_manager.init()
    embedding_client_manager.init()
    es_client_manager.init()

    # 1. MySQL 覆盖式重建
    async with meta_mysql_client_manager.session_factory() as session:
        repository = ProductRepository(session)
        await repository.clear_all()
        repository.save_products(products)
        repository.save_reviews(reviews)
        repository.save_risk_summaries(summaries)
        await session.commit()
    print("MySQL 落库完成")

    # 2. Qdrant 商品向量重建
    product_qdrant = ProductQdrantRepository(qdrant_client_manager.client)
    await product_qdrant.drop_collection()
    await product_qdrant.ensure_collection()
    texts = [product_embedding_text(p) for p in products]
    embeddings = await embedding_client_manager.client.aembed_documents(texts)
    payloads = [
        {
            "product_id": p.product_id,
            "title": p.title,
            "category_name": p.category_name,
            "brand": p.brand,
            "price": float(p.price),
            "promotion_price": float(p.promotion_price) if p.promotion_price else None,
            "rating": float(p.rating),
            "sales_30d": p.sales_30d,
        }
        for p in products
    ]
    await product_qdrant.upsert([p.product_id for p in products], embeddings, payloads)
    print("Qdrant 商品向量重建完成")

    # 3. ES 评价索引重建
    review_es = ReviewESRepository(es_client_manager.client)
    await review_es.drop_index()
    await review_es.ensure_index()
    docs = [
        {
            "review_id": r.review_id,
            "product_id": r.product_id,
            "rating": r.rating,
            "content": r.content,
            "sentiment": r.sentiment,
            "review_tags": r.review_tags_json or [],
        }
        for r in reviews
    ]
    await review_es.index_reviews(docs)
    print("ES 评价索引重建完成")

    await qdrant_client_manager.close()
    await es_client_manager.close()
    await meta_mysql_client_manager.close()
    print("SEED_DONE")


if __name__ == "__main__":
    asyncio.run(main())
