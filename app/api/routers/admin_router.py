"""
商品数据管理台路由（J3）

管理员专用（ADMIN_USERS env 判定），提供：
- GET    /api/admin/products            商品分页列表（关键词搜索）
- PATCH  /api/admin/products/{id}      商品字段编辑（白名单）
- DELETE /api/admin/products/{id}      软删商品
- GET    /api/admin/products/{id}/reviews   评价样本查看
- PATCH  /api/admin/products/{id}/risk     风险摘要编辑
- POST   /api/admin/rebuild-index       一键重建 Qdrant 向量 + ES 评价索引

重建策略：从 MySQL 读当前商品与评价全量重建索引（不重新生成演示数据），
与 seed 脚本共用同一套 embedding_text/payload 组装逻辑保证一致。
"""

from typing import Annotated, Literal
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_meta_session
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.models.product import ProductInfoMySQL, ProductReviewMySQL
from app.repositories.es.review_es_repository import ReviewESRepository
from app.repositories.mysql.meta.product_repository import ProductRepository
from app.repositories.mysql.meta.user_mysql_repository import UserMySQLRepository
from app.repositories.qdrant.product_qdrant_repository import ProductQdrantRepository
from app.services.admin_service import require_admin
from app.services.auth_service import verify_token

admin_router = APIRouter(prefix="/api/admin")


async def get_admin_user(
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[AsyncSession, Depends(get_meta_session)] = None,
) -> str:
    """从 Bearer JWT 解析用户名并要求管理员角色"""

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="需要登录")
    payload = verify_token(authorization.split(" ", 1)[1].strip())
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期")
    username = payload.get("username", "")
    await require_admin(username, UserMySQLRepository(session))
    return username


# ---------- Schema ----------


class ProductPatchSchema(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    brand: str | None = Field(default=None, max_length=128)
    price: float | None = Field(default=None, gt=0)
    promotion_price: float | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)
    sales_30d: int | None = Field(default=None, ge=0)
    status: Literal["on_sale", "off_sale"] | None = None
    attributes_json: dict | None = None


class RiskPatchSchema(BaseModel):
    risk_level: Literal["low", "medium", "high"] | None = None
    risk_tags_json: list[str] | None = None
    risk_summary: str | None = Field(default=None, max_length=2000)
    positive_summary: str | None = Field(default=None, max_length=2000)
    suitable_for: str | None = Field(default=None, max_length=1000)
    not_suitable_for: str | None = Field(default=None, max_length=1000)


def _product_dict(row: ProductInfoMySQL) -> dict:
    return {
        "product_id": row.product_id,
        "title": row.title,
        "category_name": row.category_name,
        "brand": row.brand,
        "price": float(row.price),
        "promotion_price": float(row.promotion_price) if row.promotion_price else None,
        "stock": row.stock,
        "sales_30d": row.sales_30d,
        "rating": float(row.rating),
        "review_count": row.review_count,
        "status": row.status,
        "image_url": row.image_url,
        "updated_at": row.updated_at.strftime("%Y-%m-%d %H:%M") if row.updated_at else None,
    }


# ---------- 商品 CRUD ----------


@admin_router.get("/products")
async def list_products(
    admin: Annotated[str, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_meta_session)],
    keyword: str = "",
    page: int = 1,
    size: int = 20,
):
    repository = ProductRepository(session)
    rows, total = await repository.list_all(keyword=keyword, page=page, size=size)
    return {"total": total, "items": [_product_dict(row) for row in rows]}


@admin_router.patch("/products/{product_id}")
async def patch_product(
    product_id: str,
    body: ProductPatchSchema,
    admin: Annotated[str, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_meta_session)],
):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=422, detail="没有可更新字段")
    row = await ProductRepository(session).update_product(product_id, fields)
    if row is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    # commit 会 expire 属性，之后访问 updated_at 触发同步 IO 抛 MissingGreenlet——先序列化
    result = _product_dict(row)
    await session.commit()
    return {"ok": True, "product": result}


@admin_router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    admin: Annotated[str, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_meta_session)],
):
    if not await ProductRepository(session).soft_delete_product(product_id):
        raise HTTPException(status_code=404, detail="商品不存在")
    await session.commit()
    return {"ok": True, "hint": "商品已下架软删，重建索引后从检索层移除"}


@admin_router.get("/products/{product_id}/reviews")
async def list_product_reviews(
    product_id: str,
    admin: Annotated[str, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_meta_session)],
    limit: int = 20,
):
    rows = await ProductRepository(session).list_reviews(product_id, limit=limit)
    return {
        "items": [
            {
                "review_id": row.review_id,
                "rating": row.rating,
                "content": row.content,
                "sentiment": row.sentiment,
            }
            for row in rows
        ]
    }


@admin_router.patch("/products/{product_id}/risk")
async def patch_risk(
    product_id: str,
    body: RiskPatchSchema,
    admin: Annotated[str, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_meta_session)],
):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=422, detail="没有可更新字段")
    row = await ProductRepository(session).update_risk_summary(product_id, fields)
    if row is None:
        raise HTTPException(status_code=404, detail="风险摘要不存在")
    await session.commit()
    return {"ok": True}


# ---------- 提醒规则配置（P2） ----------


@admin_router.get("/alert-rules")
async def list_alert_rules(
    admin: Annotated[str, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_meta_session)],
):
    """提醒规则列表（空表返回内置默认）"""

    from app.services.alert_rule_service import AlertRuleService

    return {"items": await AlertRuleService(session).list_rules()}


class AlertRuleSchema(BaseModel):
    rule_key: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    value_json: dict


@admin_router.put("/alert-rules/{rule_key}")
async def put_alert_rule(
    rule_key: str,
    body: AlertRuleSchema,
    admin: Annotated[str, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_meta_session)],
):
    """新增或更新提醒规则（立即生效：check_price_alerts 每次运行时读取）"""

    if rule_key != body.rule_key:
        raise HTTPException(status_code=400, detail="rule_key 不一致")
    from app.services.alert_rule_service import AlertRuleService

    await AlertRuleService(session).upsert_rule(
        body.rule_key, body.description, body.value_json
    )
    await session.commit()
    return {"ok": True}


# ---------- 一键重建索引 ----------


def _embedding_text(row: ProductInfoMySQL) -> str:
    """与 seed 脚本一致的语义入口文本（标题+品类+品牌+属性）"""

    attrs = row.attributes_json or {}
    attr_text = " ".join(f"{k}：{v}" for k, v in attrs.items())
    return f"{row.title} {row.category_name} {row.brand or ''} {attr_text}"


@admin_router.post("/rebuild-index")
async def rebuild_index(
    admin: Annotated[str, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_meta_session)],
):
    """从 MySQL 当前数据全量重建 Qdrant 商品向量与 ES 评价索引"""

    # 读全量在售商品与评价
    result = await session.execute(
        select(ProductInfoMySQL).where(
            ProductInfoMySQL.is_deleted == 0, ProductInfoMySQL.status == "on_sale"
        )
    )
    products = list(result.scalars())
    review_result = await session.execute(select(ProductReviewMySQL))
    reviews = list(review_result.scalars())

    # 1. Qdrant：清集合重建，payload/embedding_text 与 seed 完全一致
    qdrant_repo = ProductQdrantRepository(qdrant_client_manager.client)
    await qdrant_repo.drop_collection()
    await qdrant_repo.ensure_collection()
    texts = [_embedding_text(p) for p in products]
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
    await qdrant_repo.upsert(
        [str(uuid5(NAMESPACE_URL, f"product:{p.product_id}")) for p in products],
        embeddings,
        payloads,
    )

    # 2. ES：评价索引重建（含 sentiment 过滤软删商品的评价由重建自然剔除）
    es_repo = ReviewESRepository(es_client_manager.client)
    await es_repo.drop_index()
    await es_repo.ensure_index()
    live_ids = {p.product_id for p in products}
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
        if r.product_id in live_ids
    ]
    await es_repo.index_reviews(docs)

    return {"ok": True, "products": len(products), "reviews": len(docs)}
