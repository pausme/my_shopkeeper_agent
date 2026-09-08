"""
商品关注与降价提醒路由（二期 S2，PRD 4.2）

- POST   /api/shopping/watchlist          关注商品（可带目标价），幂等
- GET    /api/shopping/watchlist          关注列表（含最近提醒）
- DELETE /api/shopping/watchlist/{product_id}  取消关注（幂等）
- GET    /api/shopping/alerts             最近提醒列表

价格检查由 scripts/check_price_alerts.py 定时执行（服务器 crontab）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_meta_session
from app.models.shopping import ShoppingUserPreferenceMySQL  # noqa: F401  触发建表
from app.repositories.mysql.meta.watchlist_repository import WatchlistRepository
from app.services.auth_service import verify_token

watchlist_router = APIRouter(prefix="/api/shopping/watchlist")
alerts_router = APIRouter(prefix="/api/shopping/alerts")


async def get_watchlist_user(
    authorization: Annotated[str | None, Header()],
    session: Annotated[AsyncSession, Depends(get_meta_session)],
) -> str:
    """关注与提醒必须登录（提醒是长期用户状态）"""

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="关注功能需要登录")
    payload = verify_token(authorization.split(" ", 1)[1].strip())
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期")
    username = payload.get("username", "")
    from app.repositories.mysql.meta.user_mysql_repository import UserMySQLRepository

    user = await UserMySQLRepository(session).get_by_username(username)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return str(user.id)


class WatchSchema(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)
    target_price: float | None = Field(default=None, gt=0)


@watchlist_router.post("")
async def watch_product(
    body: WatchSchema,
    session: AsyncSession = Depends(get_meta_session),
    user_id: str = Depends(get_watchlist_user),
):
    """关注商品（幂等；重复关注时更新目标价）"""

    from app.repositories.mysql.meta.product_repository import ProductRepository

    repository = WatchlistRepository(session)
    rows = await ProductRepository(session).get_by_product_ids([body.product_id])
    if not rows:
        raise HTTPException(status_code=404, detail="商品不存在")
    row = rows[0]

    _, created = await repository.watch(
        user_id=user_id,
        product_id=body.product_id,
        product_title=row.title,
        target_price=body.target_price,
        current_price=float(row.promotion_price or row.price),
    )
    await session.commit()
    return {"ok": True, "created": created}


@watchlist_router.get("")
async def list_watchlist(
    session: AsyncSession = Depends(get_meta_session),
    user_id: str = Depends(get_watchlist_user),
):
    repository = WatchlistRepository(session)
    items = await repository.list_by_user(user_id)
    alerts = await repository.list_alerts(user_id, limit=5)
    return {"items": items, "recent_alerts": alerts}


@watchlist_router.delete("/{product_id}")
async def unwatch_product(
    product_id: str,
    session: AsyncSession = Depends(get_meta_session),
    user_id: str = Depends(get_watchlist_user),
):
    """取消关注（幂等）"""

    repository = WatchlistRepository(session)
    removed = await repository.unwatch(user_id, product_id)
    await session.commit()
    return {"ok": True, "removed": removed}


@alerts_router.get("")
async def list_alerts(
    session: AsyncSession = Depends(get_meta_session),
    user_id: str = Depends(get_watchlist_user),
):
    repository = WatchlistRepository(session)
    return {"items": await repository.list_alerts(user_id)}
