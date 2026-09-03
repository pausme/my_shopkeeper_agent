"""
用户认证服务

注册与登录的领域逻辑：PBKDF2-SHA256 密码哈希（纯 stdlib）与 JWT 签发/校验。
JWT 密钥来自环境变量 JWT_SECRET（服务器 .env 配置），未设置时启动即抛错，
避免弱密钥静默上线。
"""

import hashlib
import os
import secrets
import time

import jwt  # PyJWT

# PBKDF2 迭代次数：数十毫秒量级，足以抵御离线爆破且不拖慢登录
_PBKDF2_ITERATIONS = 120_000
# JWT 有效期（秒）：7 天
_TOKEN_TTL_SECONDS = 7 * 24 * 3600


def get_jwt_secret() -> str:
    """读取 JWT 签名密钥，未配置时显式报错"""

    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("环境变量 JWT_SECRET 未配置，无法启用用户登录")
    return secret


def hash_password(password: str) -> str:
    """生成 PBKDF2-SHA256 密码哈希，格式 iterations:salt_hex:hash_hex"""

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ITERATIONS}:{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码与存储哈希是否匹配；格式异常一律返回 False"""

    try:
        iterations_text, salt_hex, hash_hex = stored.split(":")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations_text)
        )
        return secrets.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def issue_token(user_id: int, username: str) -> str:
    """签发用户 JWT"""

    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": int(time.time()) + _TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


def verify_token(token: str) -> dict | None:
    """校验 JWT，返回载荷；无效或过期返回 None"""

    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
