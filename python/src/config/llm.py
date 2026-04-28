"""
LLM 单例模块 —— 全局复用 ChatOpenAI 实例，减少重复建连和 token 消耗。

OpenAI 自动缓存超过 1024 token 的 system prompt 前缀，因此所有 Agent
的静态系统提示词在第二次调用时几乎零成本复用。
"""

from __future__ import annotations
from functools import lru_cache
from typing import Any
import httpx
from langchain_openai import ChatOpenAI
from .settings import get_settings


@lru_cache(maxsize=4)
def _get_llm_instance(temperature: float) -> ChatOpenAI:
    """
    按温度值缓存 LLM 实例。
    大多数 Agent 使用 0.1 或 0.2，因此只有 2 个实例。
    """
    settings = get_settings()
    # 共享 HTTP 客户端，复用 TCP 连接
    client = httpx.Client(
        timeout=httpx.Timeout(60.0, connect=10.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=20),
    )
    kwargs = {
        "model": settings.openai_model,
        "api_key": settings.openai_api_key,
        "temperature": temperature,
        "http_client": client,
    }
    # 如果配置了自定义 base_url（如 DeepSeek），使用它
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**kwargs)


def get_llm(temperature: float = 0.2) -> ChatOpenAI:
    """
    获取全局复用的 ChatOpenAI 实例。

    按 temperature 缓存：0.1 / 0.2 各一个实例，HTTP 连接跨 Agent 共享。
    """
    return _get_llm_instance(temperature)


def get_structured_llm(output_model: type, temperature: float = 0.2) -> Any:
    """
    获取支持结构化输出的 LLM Runnable。

    Args:
        output_model: Pydantic 模型类，LLM 将按此 schema 输出
        temperature: LLM 温度参数
    Returns:
        可直接 invoke 的 Runnable，返回 output_model 的实例
    """
    llm = get_llm(temperature)
    return llm.with_structured_output(output_model)
