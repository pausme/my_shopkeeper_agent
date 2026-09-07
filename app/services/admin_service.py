"""
管理员判定（J3 商品数据管理台）

角色模型：user 表无 role 列（保持轻量），管理员 = 用户名命中 ADMIN_USERS 环境变量
（逗号分隔）。服务器 .env 配置如：ADMIN_USERS=dingli,ops
未配置时管理接口一律 403——安全默认拒绝，避免任何登录用户都能改商品数据。
"""

import os

from fastapi import HTTPException

from app.repositories.mysql.meta.user_mysql_repository import UserMySQLRepository


async def require_admin(username: str, user_repository: UserMySQLRepository) -> None:
    """校验用户名是否管理员，非管理员统一 403（不暴露是否存在）"""

    admins = {
        item.strip()
        for item in os.getenv("ADMIN_USERS", "").split(",")
        if item.strip()
    }
    if not admins or username not in admins:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    # 用户必须真实存在（防止管理员名单与账号体系漂移）
    user = await user_repository.get_by_username(username)
    if user is None:
        raise HTTPException(status_code=403, detail="需要管理员权限")
