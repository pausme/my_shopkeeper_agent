"""
商品业务表 ORM 模型（AI 商品决策助手）

product_info 商品主数据 / product_review 商品评价 / product_risk_summary 风险摘要
全部落在 meta 库，由 lifespan 的 Base.metadata.create_all 自动建表
"""

from sqlalchemy import JSON, DateTime, Index, String, Text, func
from sqlalchemy.dialects.mysql import DECIMAL, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProductInfoMySQL(Base):
    """商品主数据表"""

    __tablename__ = "product_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="商品业务 ID"
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="商品标题")
    category_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="类目 ID")
    category_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="类目名称")
    brand: Mapped[str | None] = mapped_column(String(128), comment="品牌")
    price: Mapped[object] = mapped_column(DECIMAL(10, 2), nullable=False, comment="原价")
    promotion_price: Mapped[object] = mapped_column(DECIMAL(10, 2), comment="到手价")
    stock: Mapped[int | None] = mapped_column(comment="库存")
    sales_30d: Mapped[int | None] = mapped_column(comment="近 30 天销量")
    rating: Mapped[object] = mapped_column(DECIMAL(3, 2), comment="平均评分")
    review_count: Mapped[int | None] = mapped_column(comment="评论数")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="on_sale", comment="on_sale/off_sale/deleted"
    )
    attributes_json: Mapped[dict | None] = mapped_column(JSON, comment="商品属性")
    detail_text: Mapped[str | None] = mapped_column(Text, comment="商品详情文本")
    image_url: Mapped[str | None] = mapped_column(String(512), comment="主图")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
    is_deleted: Mapped[int] = mapped_column(TINYINT, default=0, comment="逻辑删除")

    __table_args__ = (Index("idx_category_status_price", "category_id", "status", "price"),)


class ProductReviewMySQL(Base):
    """商品评价表"""

    __tablename__ = "product_review"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="商品 ID")
    user_id: Mapped[str | None] = mapped_column(String(64), comment="用户 ID")
    rating: Mapped[int] = mapped_column(nullable=False, comment="评分 1-5")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="评价内容")
    append_content: Mapped[str | None] = mapped_column(Text, comment="追评")
    sku_text: Mapped[str | None] = mapped_column(String(255), comment="规格信息")
    sentiment: Mapped[str | None] = mapped_column(String(32), comment="positive/neutral/negative")
    review_tags_json: Mapped[list | None] = mapped_column(JSON, comment="评价标签")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), comment="评价时间"
    )
    is_deleted: Mapped[int] = mapped_column(TINYINT, default=0, comment="逻辑删除")

    __table_args__ = (Index("idx_product_created_at", "product_id", "created_at"),)


class ProductRiskSummaryMySQL(Base):
    """商品风险摘要表（评价聚合的缓存结果表）"""

    __tablename__ = "product_risk_summary"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    risk_level: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="low/medium/high"
    )
    risk_tags_json: Mapped[list | None] = mapped_column(JSON, comment="风险标签")
    risk_summary: Mapped[str] = mapped_column(Text, nullable=False, comment="风险摘要")
    positive_summary: Mapped[str | None] = mapped_column(Text, comment="好评要点摘要")
    suitable_for: Mapped[str | None] = mapped_column(Text, comment="适合人群")
    not_suitable_for: Mapped[str | None] = mapped_column(Text, comment="不适合情况")
    sample_size: Mapped[int] = mapped_column(nullable=False, comment="评价样本量")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
    is_deleted: Mapped[int] = mapped_column(TINYINT, default=0, comment="逻辑删除")
