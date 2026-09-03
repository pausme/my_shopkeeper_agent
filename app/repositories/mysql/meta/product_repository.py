"""
商品主数据仓储

负责商品、评价、风险摘要的结构化读取：推荐链路的召回后过滤、排序与
风险展示都从这里取权威数据
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import (
    ProductInfoMySQL,
    ProductReviewMySQL,
    ProductRiskSummaryMySQL,
)


class ProductRepository:
    """商品主数据的持久化与查询"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- 写入（种子脚本使用） ----------

    async def clear_all(self):
        """清空商品域业务表，供种子脚本全量重建"""

        for model in (ProductInfoMySQL, ProductReviewMySQL, ProductRiskSummaryMySQL):
            await self.session.execute(delete(model))

    def save_products(self, products: list[ProductInfoMySQL]):
        self.session.add_all(products)

    def save_reviews(self, reviews: list[ProductReviewMySQL]):
        self.session.add_all(reviews)

    def save_risk_summaries(self, summaries: list[ProductRiskSummaryMySQL]):
        self.session.add_all(summaries)

    # ---------- 读取（推荐链路使用） ----------

    async def get_by_product_ids(self, product_ids: list[str]) -> list[ProductInfoMySQL]:
        """按商品 ID 批量取在售商品"""

        if not product_ids:
            return []
        result = await self.session.execute(
            select(ProductInfoMySQL).where(
                ProductInfoMySQL.product_id.in_(product_ids),
                ProductInfoMySQL.status == "on_sale",
                ProductInfoMySQL.is_deleted == 0,
            )
        )
        return list(result.scalars().all())

    async def list_by_category(
        self,
        category_name: str | None = None,
        price_max: float | None = None,
        price_min: float | None = None,
        limit: int = 20,
    ) -> list[ProductInfoMySQL]:
        """按类目与价格区间过滤在售商品，价格降序"""

        conditions = [
            ProductInfoMySQL.status == "on_sale",
            ProductInfoMySQL.is_deleted == 0,
        ]
        if category_name:
            conditions.append(ProductInfoMySQL.category_name == category_name)
        if price_max is not None:
            conditions.append(ProductInfoMySQL.price <= price_max)
        if price_min is not None:
            conditions.append(ProductInfoMySQL.price >= price_min)
        result = await self.session.execute(
            select(ProductInfoMySQL)
            .where(*conditions)
            .order_by(ProductInfoMySQL.sales_30d.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_risk_summary(self, product_id: str) -> ProductRiskSummaryMySQL | None:
        """读取商品风险摘要（种子阶段预计算）"""

        result = await self.session.execute(
            select(ProductRiskSummaryMySQL).where(
                ProductRiskSummaryMySQL.product_id == product_id,
                ProductRiskSummaryMySQL.is_deleted == 0,
            )
        )
        return result.scalar_one_or_none()
