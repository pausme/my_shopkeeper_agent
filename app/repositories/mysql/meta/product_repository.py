"""
商品主数据仓储

负责商品、评价、风险摘要的结构化读取：推荐链路的召回后过滤、排序与
风险展示都从这里取权威数据
"""

from sqlalchemy import delete, desc, func, select
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

    # ---------- 管理台（J3） ----------

    async def list_all(self, keyword: str = "", page: int = 1, size: int = 20) -> tuple[list, int]:
        """管理台商品分页列表，关键词匹配标题/品牌/品类，返回 (行, 总数)"""

        conditions = [ProductInfoMySQL.is_deleted == 0]
        if keyword:
            like = f"%{keyword}%"
            conditions.append(
                ProductInfoMySQL.title.like(like)
                | ProductInfoMySQL.brand.like(like)
                | ProductInfoMySQL.category_name.like(like)
            )
        total_result = await self.session.execute(
            select(func.count()).select_from(ProductInfoMySQL).where(*conditions)
        )
        total = total_result.scalar() or 0
        result = await self.session.execute(
            select(ProductInfoMySQL)
            .where(*conditions)
            .order_by(ProductInfoMySQL.product_id)
            .offset((page - 1) * size)
            .limit(size)
        )
        return list(result.scalars()), total

    async def _get_by_product_id(self, product_id: str) -> ProductInfoMySQL | None:
        """按业务键 product_id 查行（主键是自增 id，勿用 session.get）"""

        result = await self.session.execute(
            select(ProductInfoMySQL).where(ProductInfoMySQL.product_id == product_id)
        )
        row = result.scalar_one_or_none()
        return row if row and not row.is_deleted else None

    async def update_product(self, product_id: str, fields: dict) -> ProductInfoMySQL | None:
        """管理台部分更新商品字段（仅白名单键），返回更新后行"""

        row = await self._get_by_product_id(product_id)
        if row is None:
            return None
        for key, value in fields.items():
            setattr(row, key, value)
        return row

    async def soft_delete_product(self, product_id: str) -> bool:
        """软删商品（置 is_deleted，检索层靠重建索引同步）"""

        row = await self._get_by_product_id(product_id)
        if row is None:
            return False
        row.is_deleted = 1
        row.status = "deleted"
        return True

    async def list_reviews(self, product_id: str, limit: int = 20) -> list:
        """管理台查看商品评价样本"""

        result = await self.session.execute(
            select(ProductReviewMySQL)
            .where(ProductReviewMySQL.product_id == product_id)
            .order_by(desc(ProductReviewMySQL.created_at))
            .limit(limit)
        )
        return list(result.scalars())

    async def update_risk_summary(self, product_id: str, fields: dict) -> ProductRiskSummaryMySQL | None:
        """管理台编辑风险摘要（等级/标签/适合人群等）"""

        result = await self.session.execute(
            select(ProductRiskSummaryMySQL).where(
                ProductRiskSummaryMySQL.product_id == product_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        for key, value in fields.items():
            setattr(row, key, value)
        return row

    async def get_risk_summary(self, product_id: str) -> ProductRiskSummaryMySQL | None:
        """读取商品风险摘要（种子阶段预计算）"""

        result = await self.session.execute(
            select(ProductRiskSummaryMySQL).where(
                ProductRiskSummaryMySQL.product_id == product_id,
                ProductRiskSummaryMySQL.is_deleted == 0,
            )
        )
        return result.scalar_one_or_none()
