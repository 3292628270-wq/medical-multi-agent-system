"""
Diagnosis Agent — 基于结构化患者数据的鉴别诊断。

职责：
  - 先通过 GraphRAG 知识图谱做确定性症状-疾病检索
  - 将检索结果注入 LLM，结合患者数据做最终诊断推理
  - 生成带置信度评分的排序鉴别诊断列表
  - 当信息不足时建议补充检查
"""

from __future__ import annotations
import json
import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..config.settings import get_settings
from ..models.llm_outputs import DiagnosisOutput
from ..services.graphrag_service import get_graphrag_service

logger = structlog.get_logger(__name__)

DIAGNOSIS_SYSTEM_PROMPT = """你是一位专家级诊断医师，正在执行鉴别诊断。根据提供的结构化患者信息和知识图谱检索结果，给出全面的鉴别诊断。

输出JSON格式，包含：
- primary_diagnosis: 最可能的诊断 (disease_name, icd10_hint, confidence, evidence, reasoning)
- differential_list: 2-3个鉴别诊断，按可能性排序
- recommended_tests: 建议进一步检查以确认或排除诊断
- clinical_notes: 整体临床印象
- knowledge_sources: 引用的医学知识来源（包含"GraphRAG知识图谱"）
- needs_more_info: 是否缺少关键信息 (true/false)

规则：
- 参考知识图谱检索结果，但如果有临床依据也可超出图谱范围
- 置信度在 0 到 1 之间
- 至少提供 2-3 个鉴别诊断
- 从患者数据中列出支持每个诊断的证据
- 如果缺少关键信息，将 needs_more_info 设为 true"""


def diagnosis_agent(state) -> dict:
    """
    LangGraph 节点：根据患者信息生成鉴别诊断。
    先调 GraphRAG 做确定性检索，再将结果注入 LLM 做最终推理。
    读取：state.patient_info
    写入：state.diagnosis, state.needs_more_info, state.current_agent
    """
    logger.info("diagnosis_agent.start", retry_count=state.diagnosis_retry_count)

    patient_info = state.patient_info
    if not patient_info:
        return {
            "diagnosis": None,
            "needs_more_info": True,
            "current_agent": "diagnosis",
            "errors": state.errors + ["No patient info available for diagnosis"],
        }

    # ---- Step 1: GraphRAG 确定性检索 ----
    symptoms = [s["name"] for s in patient_info.get("symptoms", []) if s.get("name")]
    chief = patient_info.get("chief_complaint", "")
    rag_context = ""
    if symptoms:
        try:
            rag = get_graphrag_service()
            candidates = rag.find_diseases_by_symptoms(symptoms)
            rag_context = json.dumps(
                {"匹配症状": symptoms, "知识图谱候选疾病": candidates},
                indent=2,
                ensure_ascii=False,
            )
            logger.info("diagnosis_agent.graphrag_hits", count=len(candidates))
        except Exception as e:
            logger.warning("diagnosis_agent.graphrag_fallback", error=str(e))

    # ---- Step 2: LLM 推理 ----
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.2,
    )
    structured_llm = llm.with_structured_output(DiagnosisOutput)

    patient_summary = json.dumps(patient_info, indent=2, ensure_ascii=False)

    # 将知识图谱检索结果注入 prompt
    if rag_context:
        prompt = (
            f"患者信息：\n\n{patient_summary}\n\n"
            f"知识图谱检索结果（仅供参考）：\n\n{rag_context}\n\n"
            f"请结合患者数据和知识图谱参考，给出鉴别诊断。"
        )
    else:
        prompt = f"患者信息：\n\n{patient_summary}\n\n请给出鉴别诊断。"

    messages = [
        SystemMessage(content=DIAGNOSIS_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        output: DiagnosisOutput = structured_llm.invoke(messages)
        diagnosis_data = output.model_dump(mode="json")
        needs_more = diagnosis_data.pop("needs_more_info", False)

        logger.info(
            "diagnosis_agent.success",
            primary=diagnosis_data.get("primary_diagnosis", {}).get("disease_name"),
        )
        return {
            "diagnosis": diagnosis_data,
            "needs_more_info": needs_more,
            "current_agent": "diagnosis",
        }
    except Exception as e:
        logger.error("diagnosis_agent.error", error=str(e))
        return {
            "diagnosis": None,
            "needs_more_info": False,
            "current_agent": "diagnosis",
            "errors": state.errors + [f"诊断生成失败: {e}"],
        }
