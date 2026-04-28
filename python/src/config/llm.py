"""
LLM 单例模块 —— 全局复用 ChatOpenAI 实例，减少重复建连和 token 消耗。

支持结构化输出（OpenAI JSON mode / Function Calling），
DeepSeek 等不兼容模型自动回退到 Prompt + json.loads() 方式。
"""

from __future__ import annotations
import json
import structlog
from functools import lru_cache
from typing import Any
import httpx
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import HumanMessage, SystemMessage
from .settings import get_settings

logger = structlog.get_logger(__name__)


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


def _try_structured_output(llm, output_model, messages):
    """尝试使用原生 structured output（OpenAI JSON mode）。"""
    structured = llm.with_structured_output(output_model)
    return structured.invoke(messages)


def _parse_json_output(raw_text: str) -> dict:
    """从 LLM 文本响应中提取 JSON（兼容 markdown fence）。"""
    text = raw_text.strip()
    # 剥离 markdown fence
    if text.startswith("```"):
        lines = text.split("\n")
        # 跳过首行 ```json 或 ```
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3].strip()
    return json.loads(text)


def _model_schema_text(model: type) -> str:
    """将 Pydantic 模型的字段结构生成为 LLM 可读的 JSON 示例。"""
    from pydantic import BaseModel

    def _field_info(field_name: str, field_info) -> dict:
        if hasattr(field_info.annotation, "model_fields"):
            # 嵌套 BaseModel
            return _model_to_example(field_info.annotation)
        if hasattr(field_info.annotation, "__origin__") and field_info.annotation.__origin__ is list:
            args = getattr(field_info.annotation, "__args__", [])
            if args and hasattr(args[0], "model_fields"):
                return [_model_to_example(args[0])]
            return [f"<{field_name} value>"]
        if field_info.annotation in (str, int, float, bool):
            t = {str: "<string>", int: 0, float: 0.0, bool: False}
            return t.get(field_info.annotation, "<value>")
        # Optional types
        if hasattr(field_info.annotation, "__origin__"):
            return None
        return f"<{field_name}>"

    def _model_to_example(model_cls) -> dict:
        example = {}
        for name, info in model_cls.model_fields.items():
            example[name] = _field_info(name, info)
        return example

    schema = _model_to_example(model)
    return json.dumps(schema, indent=2, ensure_ascii=False)


def _fallback_structured_output(llm, output_model, messages):
    """
    Prompt-based JSON 提取（DeepSeek 等不兼容 structured output 的模型）。
    将 Pydantic schema 注入 prompt，确保 LLM 按正确格式输出。
    """
    schema_text = _model_schema_text(output_model)

    augmented = list(messages)
    augmented.append(HumanMessage(
        content=f"请严格按照以下 JSON schema 格式返回结果，只返回有效 JSON，不要包含 markdown 代码块标记或其他文字：\n\n{schema_text}"
    ))

    response = llm.invoke(augmented)
    data = _parse_json_output(response.content)
    return output_model(**data)


def get_structured_llm(output_model: type, temperature: float = 0.2) -> Any:
    """
    获取支持结构化输出的 Runnable。

    先尝试 with_structured_output（OpenAI native），
    如果模型不支持（如 DeepSeek），自动回退到 Prompt + json.loads()。

    Args:
        output_model: Pydantic 模型类，LLM 将按此 schema 输出
        temperature: LLM 温度参数
    Returns:
        可直接 invoke 的 Runnable，接收 messages 返回 output_model 实例
    """
    llm = get_llm(temperature)

    def _invoke(messages):
        try:
            return _try_structured_output(llm, output_model, messages)
        except Exception as e:
            err_msg = str(e)
            if "response_format" in err_msg or "unavailable" in err_msg:
                logger.info("llm.structured_output_fallback",
                            reason="模型不支持原生structured output，回退Prompt方式")
                return _fallback_structured_output(llm, output_model, messages)
            raise

    return RunnableLambda(_invoke)
