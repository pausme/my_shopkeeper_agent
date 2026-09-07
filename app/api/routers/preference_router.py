"""
偏好中心路由（二期 S1-1，PRD 4.1）

- POST   /api/shopping/preferences                     新增或更新偏好（批量）
- GET    /api/shopping/preferences                     当前用户偏好画像
- PATCH  /api/shopping/preferences/{preference_key}    修改单条
- DELETE /api/shopping/preferences/{preference_key}    删除单条

身份要求：登录 JWT（偏好是用户画像，匿名无归属）。读写均带 user_id 隔离。
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_meta_session
from app.repositories.mysql.meta.shopping_repositories import (
    ShoppingSessionRepository,
)
from app.repositories.mysql.meta.user_mysql_repository import UserMySQLRepository
from app.services.auth_service import verify_token

preference_router = APIRouter(prefix="/api/shopping/preferences")


async def get_preference_repository(
    session: Annotated[AsyncSession, Depends(get_meta_session)],
) -> ShoppingSessionRepository:
    return ShoppingSessionRepository(session)


async def get_preference_user(
    authorization: Annotated[str | None, Header()],
    session: Annotated[AsyncSession, Depends(get_meta_session)],
) -> str:
    """偏好必须有登录身份：从 JWT 解析 user_id（数字主键转字符串）"""

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="偏好中心需要登录")
    payload = verify_token(authorization.split(" ", 1)[1].strip())
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期")
    username = payload.get("username", "")
    user = await UserMySQLRepository(session).get_by_username(username)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return str(user.id)


class PreferenceItem(BaseModel):
    preference_key: str = Field(min_length=1, max_length=64)
    preference_value: str = Field(min_length=1, max_length=255)
    source: Literal["explicit", "inferred"] = "explicit"
    confidence: float | None = Field(default=None, ge=0, le=1)


class PreferenceBatchSchema(BaseModel):
    items: list[PreferenceItem] = Field(min_length=1, max_length=20)


@preference_router.post("")
async def save_preferences(
    body: PreferenceBatchSchema,
    session: Annotated[AsyncSession, Depends(get_meta_session)],
    user_id: str = Depends(get_preference_user),
    repository: ShoppingSessionRepository = Depends(get_preference_repository),
):
    """新增或更新偏好（幂等：同 key 覆盖）"""

    for item in body.items:
        await repository.upsert_preference(
            user_id, item.preference_key, item.preference_value,
            source=item.source, confidence=item.confidence,
        )
    await session.commit()
    return {"ok": True, "saved": len(body.items)}


@preference_router.get("")
async def list_preferences(
    session: Annotated[AsyncSession, Depends(get_meta_session)],
    user_id: str = Depends(get_preference_user),
    repository: ShoppingSessionRepository = Depends(get_preference_repository),
):
    """当前用户偏好画像"""

    return {"items": await repository.list_preferences(user_id)}


@preference_router.patch("/{preference_key}")
async def patch_preference(
    preference_key: str,
    body: PreferenceItem,
    session: Annotated[AsyncSession, Depends(get_meta_session)],
    user_id: str = Depends(get_preference_user),
    repository: ShoppingSessionRepository = Depends(get_preference_repository),
):
    """修改单条偏好（不存在则创建）"""

    await repository.upsert_preference(
        user_id, preference_key, body.preference_value,
        source=body.source, confidence=body.confidence,
    )
    await session.commit()
    return {"ok": True}


@preference_router.delete("/{preference_key}")
async def delete_preference(
    preference_key: str,
    session: Annotated[AsyncSession, Depends(get_meta_session)],
    user_id: str = Depends(get_preference_user),
    repository: ShoppingSessionRepository = Depends(get_preference_repository),
):
    """删除单条偏好"""

    deleted = await repository.delete_preference(user_id, preference_key)
    await session.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="偏好不存在")
    return {"ok": True}
