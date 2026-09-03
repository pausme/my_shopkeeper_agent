"""
FastAPI 应用入口

AI 商品决策助手（PickMate AI）：注册生命周期、挂载认证与导购路由，
并为每个请求注入 request_id 便于链路追踪。
"""

import uuid

from fastapi import FastAPI, Request

from app.api.lifespan import lifespan
from app.api.routers.auth_router import auth_router
from app.api.routers.shopping_router import shopping_router
from app.core.context import request_id_ctx_var

# lifespan 交给 FastAPI 管理，用于在服务启动和关闭时统一初始化与释放外部客户端
app = FastAPI(lifespan=lifespan)

# 用户认证路由
app.include_router(auth_router)
# AI 商品决策助手（导购）路由
app.include_router(shopping_router)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    # 请求被处理之前
    request_id = uuid.uuid4()
    request_id_ctx_var.set(request_id)
    response = await call_next(request)
    # 请求被处理之后
    return response
