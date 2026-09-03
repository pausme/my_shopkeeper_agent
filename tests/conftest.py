"""
pytest 全局夹具

app 配置模块在导入时会解析 ${oc.env:LLM_API_KEY}，
测试环境没有真实密钥，这里在收集阶段先注入占位值，保证模块可导入。
"""

import os

os.environ.setdefault("LLM_API_KEY", "test-key-for-pytest")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-0123456789abcdef")
