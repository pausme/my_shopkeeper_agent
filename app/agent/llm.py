"""
电商问数 Agent 使用的大模型实例

支持多供应商按优先级降级：
LLM_BASE_URL / LLM_MODEL_NAME / LLM_API_KEY 三个环境变量均支持逗号分隔的多组值，
按序组合成供应商列表（数量不足时循环复用已有值）。
调用时优先使用上一个成功供应商（粘性），失败或超时自动切换下一个，全部失败才抛错。
只配置单组值时行为与单一供应商完全一致。
"""

import asyncio
import os
import re

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableLambda

from app.conf.app_config import app_config
from app.core.log import logger

# 单个供应商的最长等待时间（秒），超时视为失败并切换下一个
PROVIDER_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT", "180"))


def _parse_list(raw: str) -> list[str]:
    """把逗号分隔的环境变量解析成列表，去掉空项"""

    return [item.strip() for item in raw.split(",") if item.strip()]


def _build_providers() -> list[dict]:
    """按环境变量组装供应商列表；未配置的维度回退到 yaml 默认值"""

    base_urls = _parse_list(os.getenv("LLM_BASE_URL", "")) or [app_config.llm.base_url]
    model_names = _parse_list(os.getenv("LLM_MODEL_NAME", "")) or [
        app_config.llm.model_name
    ]
    api_keys = _parse_list(os.getenv("LLM_API_KEY", "")) or [app_config.llm.api_key]

    # 以最长的维度为准，短维度循环复用（例如三组 base_url 配一个 key）
    count = max(len(base_urls), len(model_names), len(api_keys))
    providers = []
    for index in range(count):
        providers.append(
            {
                "base_url": base_urls[index % len(base_urls)],
                "model_name": model_names[index % len(model_names)],
                "api_key": api_keys[index % len(api_keys)],
            }
        )
    return providers


def _provider_label(provider: dict) -> str:
    """日志里展示的供应商标识：模型名 + 域名，不含密钥"""

    host = re.sub(r"^https?://", "", provider["base_url"]).split("/")[0]
    return f"{provider['model_name']}@{host}"


_providers = _build_providers()
_models = [
    init_chat_model(
        model=provider["model_name"],
        # 硅基流动等服务兼容 OpenAI 协议时，可以使用 openai provider 接入
        model_provider="openai",
        base_url=provider["base_url"],
        api_key=provider["api_key"],
        # 字段扩展、SQL 生成更看重稳定性，所以这里关闭随机发散
        temperature=0,
    )
    for provider in _providers
]

# 粘性索引：记录最近一次成功的供应商，后续调用优先走它
_last_good_index = 0

if len(_models) > 1:
    logger.info(
        f"LLM 多供应商已启用: {' -> '.join(_provider_label(p) for p in _providers)}"
    )


async def _ainvoke_with_fallback(prompt_value):
    """按优先级尝试各供应商，超时或异常自动切换；全部失败时抛出汇总错误"""

    global _last_good_index

    order = sorted(range(len(_models)), key=lambda i: i != _last_good_index)
    errors = []
    for index in order:
        try:
            result = await asyncio.wait_for(
                _models[index].ainvoke(prompt_value), timeout=PROVIDER_TIMEOUT_SECONDS
            )
            if index != _last_good_index:
                logger.info(f"LLM 供应商切换为 {_provider_label(_providers[index])}")
                _last_good_index = index
            return result
        except Exception as exc:  # noqa: BLE001
            label = _provider_label(_providers[index])
            errors.append(f"{label}: {exc}")
            logger.warning(f"LLM 供应商失败，尝试切换下一个：{label}: {exc}")

    raise RuntimeError("所有 LLM 供应商均失败：" + " | ".join(errors))


# 节点管道中 `prompt | llm | parser` 只依赖 ainvoke，用 RunnableLambda 包装即可无缝替换
llm = RunnableLambda(_ainvoke_with_fallback)

if __name__ == "__main__":
    # 本地快速验证各供应商是否可正常调用：uv run python -m app.agent.llm
    from langchain_core.messages import HumanMessage

    print(asyncio.run(llm.ainvoke([HumanMessage(content="你好")])))
