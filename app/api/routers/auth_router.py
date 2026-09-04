"""
用户认证路由

- POST /api/auth/register  注册（PBKDF2 密码哈希 + JWT 签发）
- POST /api/auth/login     登录
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import enforce_rate_limit
from app.repositories.mysql.meta.user_mysql_repository import UserMySQLRepository
from app.services.auth_service import hash_password, issue_token, verify_password

auth_router = APIRouter(prefix="/api/auth")


async def get_meta_session_dependency():
    """认证接口使用的 Meta MySQL Session"""

    from app.clients.mysql_client_manager import meta_mysql_client_manager

    async with meta_mysql_client_manager.session_factory() as session:
        yield session


# ---------- 请求模型 ----------


class RegisterSchema(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginSchema(BaseModel):
    username: str
    password: str


# ---------- 认证端点 ----------


@auth_router.post("/register")
async def register(
    body: RegisterSchema,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_meta_session_dependency)],
):
    """注册新用户：用户名查重后落库并直接签发令牌"""

    # findings #6：注册/登录限流（每 IP 每分钟 5 次）
    enforce_rate_limit(f"auth:{request.client.host if request.client else 'unknown'}", 5, 60)

    # R3：用户名统一 strip，注册/登录共用同一套规范化，防尾随空格产生影子账号
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=422, detail="用户名不能为空")

    repository = UserMySQLRepository(session)
    if await repository.get_by_username(username):
        raise HTTPException(status_code=409, detail="用户名已被占用")
    user = await repository.create(username, hash_password(body.password))
    await session.commit()
    return {"token": issue_token(user.id, user.username), "username": user.username}


@auth_router.post("/login")
async def login(
    body: LoginSchema,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_meta_session_dependency)],
):
    """校验用户名密码，签发 JWT"""

    enforce_rate_limit(f"auth:{request.client.host if request.client else 'unknown'}", 5, 60)

    # R3：登录侧同样 strip，与注册规范化一致
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=422, detail="用户名不能为空")

    repository = UserMySQLRepository(session)
    user = await repository.get_by_username(username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": issue_token(user.id, user.username), "username": user.username}
