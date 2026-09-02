"""
问数接口请求体定义

集中声明 API 层输入输出的数据结构，让路由函数只处理业务流程，
字段校验和 OpenAPI 文档生成交给 Pydantic 与 FastAPI 完成。
"""

from typing import Literal

from pydantic import BaseModel


class HistoryMessage(BaseModel):
    """多轮问数的历史消息，用于让模型理解上下文指代"""

    role: Literal["user", "assistant"]
    content: str


class QuerySchema(BaseModel):
    """`/api/query` 请求体，承载用户输入的自然语言问题和可选的最近对话"""

    # 前端请求体中的 query 字段，例如 {"query": "统计华北地区销售额"}
    query: str
    # 最近几轮对话，帮助模型理解"那华东呢"这类指代；不传则按独立问题处理
    history: list[HistoryMessage] = []
