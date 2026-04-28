"""
Intake Agent — 患者信息采集与结构化。

职责：
  - 解析原始患者描述文本，提取结构化信息
  - 将自由文本标准化为 FHIR 对齐格式
  - 校验关键字段完整性
"""

from __future__ import annotations
import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..config.settings import get_settings
from ..models.llm_outputs import IntakeOutput

logger = structlog.get_logger(__name__)

INTAKE_SYSTEM_PROMPT = """你是一位专业的医疗接诊专家。从提供的临床叙述中提取结构化的患者信息，输出JSON格式。

提取规则：
- 如果某个字段未提及，使用合理的默认值或 null
- 年龄必须是正整数，如果模糊不清则从上下文中推断
- 即使主诉未明确说明，也需根据上下文推断
- 药物名称使用通用名，剂量和频率按原文提取"""


def intake_agent(state) -> dict:
    """
    LangGraph 节点：将原始患者输入解析为结构化数据。
    读取：state.raw_input
    写入：state.patient_info, state.current_agent
    """
    logger.info("intake_agent.start", raw_input_len=len(state.raw_input or ""), retry_count=state.diagnosis_retry_count)

    raw = state.raw_input
    if not raw:
        return {
            "patient_info": None,
            "current_agent": "intake",
            "errors": state.errors + ["No raw input provided to Intake Agent"],
        }

    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.1,
    )
    # 使用结构化输出，LLM自动返回校验后的IntakeOutput对象
    structured_llm = llm.with_structured_output(IntakeOutput)

    messages = [
        SystemMessage(content=INTAKE_SYSTEM_PROMPT),
        HumanMessage(content=f"患者临床叙述：\n\n{raw}"),
    ]

    try:
        output: IntakeOutput = structured_llm.invoke(messages)
        patient_dict = output.model_dump(mode="json")

        logger.info("intake_agent.success", patient_name=output.name)
        return {
            "patient_info": patient_dict,
            "current_agent": "intake",
            # 递增诊断循环计数，防止无限循环
            "diagnosis_retry_count": state.diagnosis_retry_count + 1,
        }
    except Exception as e:
        logger.error("intake_agent.error", error=str(e))
        return {
            "patient_info": None,
            "current_agent": "intake",
            "errors": state.errors + [f"Intake提取失败: {e}"],
        }
