"""
用户认证与会话持久化路由

- POST /api/auth/register  注册（首个注册用户自动成为管理员身份，仅用于标记）
- POST /api/auth/login     登录，签发 JWT
- GET  /api/conversations  列出当前用户的会话
- PUT  /api/conversations/{id}  整体保存会话（消息整块覆盖，前端防抖后调用）
- DELETE /api/conversations/{id}  删除会话

鉴权方式：Authorization: Bearer <JWT>；/api/query 延续 X-API-Token 共享令牌
（访问门槛），用户级隔离由会话接口的 JWT 保证。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.mysql.meta.conversation_mysql_repository import (
    ConversationMySQLRepository,
)
from app.repositories.mysql.meta.user_mysql_repository import UserMySQLRepository
from app.services.auth_service import (
    hash_password,
    issue_token,
    verify_password,
    verify_token,
)

auth_router = APIRouter(prefix="/api/auth")
conversation_router = APIRouter(prefix="/api/conversations")


# ---------- 请求/响应模型 ----------


class RegisterSchema(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginSchema(BaseModel):
    username: str
    password: str


class MessagePayload(BaseModel):
    id: str
    role: str
    content: str
    createdAt: int
    status: str | None = None
    steps: list[dict] | None = None
    result: object = None
    error: str | None = None


class ConversationPayload(BaseModel):
    id: str = Field(min_length=8, max_length=64)
    title: str = Field(max_length=128, default="新会话")
    messages: list[MessagePayload] = Field(max_length=200)


# ---------- 依赖 ----------


async def get_meta_session_dependency():
    """会话级 Meta MySQL Session（与 dependencies.py 的请求级 Session 分开，避免循环依赖）"""

    from app.clients.mysql_client_manager import meta_mysql_client_manager

    async with meta_mysql_client_manager.session_factory() as session:
        yield session


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[AsyncSession, Depends(get_meta_session_dependency)] = None,
):
    """从 Bearer JWT 解析当前用户；无效则 401"""

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少登录凭证")
    token = authorization.split(" ", 1)[1].strip()
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    repository = UserMySQLRepository(session)
    user = await repository.get_by_username(payload.get("username", ""))
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


# ---------- 认证端点 ----------


@auth_router.post("/register")
async def register(
    body: RegisterSchema,
    session: Annotated[AsyncSession, Depends(get_meta_session_dependency)],
):
    """注册新用户：用户名查重后落库并直接签发令牌"""

    repository = UserMySQLRepository(session)
    if await repository.get_by_username(body.username):
        raise HTTPException(status_code=409, detail="用户名已被占用")
    user = await repository.create(body.username, hash_password(body.password))
    await session.commit()
    return {"token": issue_token(user.id, user.username), "username": user.username}


@auth_router.post("/login")
async def login(
    body: LoginSchema,
    session: Annotated[AsyncSession, Depends(get_meta_session_dependency)],
):
    """校验用户名密码，签发 JWT"""

    repository = UserMySQLRepository(session)
    user = await repository.get_by_username(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": issue_token(user.id, user.username), "username": user.username}


# ---------- 会话端点 ----------


@conversation_router.get("")
async def list_conversations(
    user: Annotated[object, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_meta_session_dependency)],
):
    """列出当前用户全部会话（按最近更新倒序）"""

    repository = ConversationMySQLRepository(session)
    return await repository.list_by_user(user.id)


@conversation_router.put("/{conversation_id}")
async def save_conversation(
    conversation_id: str,
    body: ConversationPayload,
    user: Annotated[object, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_meta_session_dependency)],
):
    """创建或整体覆盖会话；只允许操作自己的会话"""

    if conversation_id != body.id:
        raise HTTPException(status_code=400, detail="路径与会话 ID 不一致")

    repository = ConversationMySQLRepository(session)
    await repository.upsert(user.id, body.id, body.title, [m.model_dump() for m in body.messages])
    await session.commit()
    return {"ok": True}


@conversation_router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: Annotated[object, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_meta_session_dependency)],
):
    """删除属主会话"""

    repository = ConversationMySQLRepository(session)
    deleted = await repository.delete(user.id, conversation_id)
    await session.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}
