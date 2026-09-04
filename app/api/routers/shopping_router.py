"""
AI 商品决策助手（导购）路由

- POST /api/shopping/query            导购问答（SSE：progress/clarification/recommendation/comparison/error）
- POST /api/shopping/feedback         推荐反馈
- GET  /api/shopping/sessions         会话列表
- GET  /api/shopping/sessions/{id}    会话详情（消息历史）
- DELETE /api/shopping/sessions/{id}  删除会话（隐私控制）
- POST /api/shopping/events           行为埋点上报
- POST /api/shopping/compare          指定商品横向对比
- GET  /api/shopping/products/{id}/summary  商品摘要与风险

接口规则（PRD）：不暴露 SQL/提示词/内部向量分值；反馈可追溯 session_id + message_id
"""

import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.api.dependencies import get_shopping_service
from app.repositories.mysql.meta.user_mysql_repository import UserMySQLRepository
from app.services.auth_service import verify_token
from app.services.shopping_agent_service import ShoppingAgentService

shopping_router = APIRouter(prefix="/api/shopping")


async def get_user_scope(
    service: Annotated[ShoppingAgentService, Depends(get_shopping_service)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_token: Annotated[str | None, Header()] = None,
):
    """请求身份解析（安全整改：见 docs/security-and-usability-findings.md #2/#3）

    - 合法用户 JWT 优先：服务端解析出 user_id 并返回，绝不信任客户端自传的 X-User-Id
    - 否则校验共享令牌（API_TOKEN 未设置时放行，本地开发）；
      共享令牌访问无个人身份，返回 None——会话类接口对无身份请求不返回私有数据
    - 服务器设置了 API_TOKEN 且两者都无效时 401
    """

    if authorization and authorization.lower().startswith("bearer "):
        payload = verify_token(authorization.split(" ", 1)[1].strip())
        if payload:
            user = await UserMySQLRepository(service.session).get_by_username(
                payload.get("username", "")
            )
            if user is not None:
                return str(user.id)

    expected = os.getenv("API_TOKEN")
    if expected and x_api_token != expected:
        raise HTTPException(status_code=401, detail="Invalid API token")
    return None


class ShoppingQuerySchema(BaseModel):
    query: str
    session_id: str | None = None
    history: list[dict] = []
    selected_product_ids: list[str] = []
    scene_tag: str | None = None
    # 本会话已经历的追问轮数：前端在用户回答追问后随下一轮请求带回
    clarification_count: int = 0


class FeedbackSchema(BaseModel):
    session_id: str
    message_id: str | None = None
    feedback_type: Literal[
        # PRD 9.4 反馈六项
        "helpful",
        "unhelpful",
        "not_accurate",
        "too_expensive",
        "too_few",
        "not_understand",
        "out_of_stock",
    ]
    product_id: str | None = None
    comment: str | None = None


class CompareSchema(BaseModel):
    product_ids: list[str] = Field(min_length=2, max_length=5)
    query: str | None = None
    session_id: str | None = None


@shopping_router.post(
    "/query", dependencies=[Depends(get_user_scope)]
)
async def shopping_query(
    body: ShoppingQuerySchema,
    service: Annotated[ShoppingAgentService, Depends(get_shopping_service)],
    user_id: Annotated[str | None, Depends(get_user_scope)] = None,
):
    """发起导购问答：流式返回追问、召回、分析、推荐与对比"""

    return StreamingResponse(
        service.query(
            body.query,
            session_id=body.session_id,
            history=body.history,
            selected_product_ids=body.selected_product_ids,
            scene_tag=body.scene_tag,
            user_id=user_id,
            clarification_count=body.clarification_count,
        ),
        media_type="text/event-stream",
    )


@shopping_router.post("/feedback", dependencies=[Depends(get_user_scope)])
async def shopping_feedback(
    body: FeedbackSchema,
    service: Annotated[ShoppingAgentService, Depends(get_shopping_service)],
    user_id: Annotated[str | None, Depends(get_user_scope)] = None,
):
    """记录用户对推荐结果的反馈"""

    feedback_id = await service.shopping_session_repository.save_feedback(
        body.session_id,
        body.message_id,
        body.feedback_type,
        product_id=body.product_id,
        user_id=user_id,
        comment=body.comment,
    )
    await service.session.commit()
    return {"ok": True, "feedback_id": feedback_id}


@shopping_router.get("/sessions", dependencies=[Depends(get_user_scope)])
async def shopping_sessions(
    service: Annotated[ShoppingAgentService, Depends(get_shopping_service)],
    user_id: Annotated[str | None, Depends(get_user_scope)] = None,
):
    """获取当前身份的历史导购会话；无身份（纯共享令牌）不返回任何私有会话"""

    return await service.shopping_session_repository.list_sessions(user_id)


@shopping_router.get("/sessions/{session_id}", dependencies=[Depends(get_user_scope)])
async def shopping_session_detail(
    session_id: str,
    service: Annotated[ShoppingAgentService, Depends(get_shopping_service)],
    user_id: Annotated[str | None, Depends(get_user_scope)] = None,
):
    """获取单个会话的消息历史（属主校验：登录身份不匹配时视为不存在）"""

    owner = await service.shopping_session_repository.get_session_owner(session_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if user_id is not None and owner != user_id:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = await service.shopping_session_repository.get_session_messages(session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"session_id": session_id, "messages": messages}


class EventSchema(BaseModel):
    """前端行为埋点（M8.3）：点击/曝光等事件的统一上报入口"""

    session_id: str
    message_id: str | None = None
    event_type: str = Field(min_length=1, max_length=64)
    product_id: str | None = None
    event_data: dict = {}


@shopping_router.post("/events", dependencies=[Depends(get_user_scope)])
async def shopping_event(
    body: EventSchema,
    service: Annotated[ShoppingAgentService, Depends(get_shopping_service)],
    user_id: Annotated[str | None, Depends(get_user_scope)] = None,
):
    """记录前端行为埋点事件（商品点击等）"""

    event_data = dict(body.event_data)
    if body.product_id:
        event_data["product_id"] = body.product_id
    await service.shopping_session_repository.save_event(
        body.session_id, body.message_id, user_id, body.event_type, event_data
    )
    await service.session.commit()
    return {"ok": True}


@shopping_router.delete("/sessions/{session_id}", dependencies=[Depends(get_user_scope)])
async def delete_shopping_session(
    session_id: str,
    service: Annotated[ShoppingAgentService, Depends(get_shopping_service)],
):
    """删除导购会话（M9.3 隐私控制：用户可清除自己的咨询历史）"""

    deleted = await service.shopping_session_repository.delete_session(session_id)
    await service.session.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@shopping_router.post("/compare", dependencies=[Depends(get_user_scope)])
async def shopping_compare(
    body: CompareSchema,
    service: Annotated[ShoppingAgentService, Depends(get_shopping_service)],
):
    """对多个商品生成结构化横向对比"""

    table = await service.compare_products(body.product_ids)
    if table is None:
        raise HTTPException(status_code=404, detail="商品不存在或数量不足")
    return {"session_id": body.session_id, "comparison": table}


@shopping_router.get(
    "/products/{product_id}/summary", dependencies=[Depends(get_user_scope)]
)
async def shopping_product_summary(
    product_id: str,
    service: Annotated[ShoppingAgentService, Depends(get_shopping_service)],
):
    """返回商品简介、评价摘要和风险提示"""

    summary = await service.product_summary(product_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return summary
