"""
Coding Agent — ICD-10自动编码与DRGs分组。

职责：
  - 先由LLM根据诊断文本生成ICD-10编码建议
  - 再通过icd10_service做确定性编码校验，不存在的编码回退搜索
  - DRG分组优先用icd10_service查询
"""

from __future__ import annotations
import json
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from ..config.llm import get_structured_llm
from ..models.llm_outputs import CodingOutput
from ..services.icd10_service import lookup_icd10, search_icd10_by_text, get_drg_group

logger = structlog.get_logger(__name__)

CODING_SYSTEM_PROMPT = """你是一位持有认证的医学编码专家 (CCS)，精通ICD-10-CM和DRG分组。根据诊断信息和治疗详情，分配准确的医学编码。

输出JSON格式，包含：
- primary_icd10: 主要ICD-10编码 (code, description, confidence, category)
- secondary_icd10_codes: 次要编码列表（合并症、并发症）
- drg_group: DRG分组 (drg_code, description, weight, mean_los)
- coding_notes: 编码选择理由
- coding_confidence: 整体编码置信度

规则：
- 使用最具体的ICD-10-CM编码（第4-7位字符级别）
- 主要编码应匹配主要诊断
- 次要编码包含合并症和并发症
- 置信度反映编码分配的确定程度"""


def coding_agent(state) -> dict:
    """
    LangGraph 节点：分配ICD-10编码和DRG分组。
    先LLM生成编码，再用icd10_service做确定性校验。
    读取：state.diagnosis, state.treatment_plan
    写入：state.coding_result, state.current_agent
    """
    logger.info("coding_agent.start")

    diagnosis = state.diagnosis
    treatment = state.treatment_plan

    if not diagnosis:
        return {
            "coding_result": None,
            "current_agent": "coding",
            "errors": state.errors + ["No diagnosis available for coding"],
        }

    # ---- Step 1: LLM 生成编码 ----
    structured_llm = get_structured_llm(CodingOutput, temperature=0.1)

    context = json.dumps(
        {"diagnosis": diagnosis, "treatment_plan": treatment},
        indent=2,
        ensure_ascii=False,
    )

    messages = [
        SystemMessage(content=CODING_SYSTEM_PROMPT),
        HumanMessage(
            content=f"待编码的临床数据：\n\n{context}\n\n请分配ICD-10编码和DRG分组。"
        ),
    ]

    try:
        output: CodingOutput = structured_llm.invoke(messages)
        coding_data = output.model_dump(mode="json")

        # ---- Step 2: 确定性ICD-10编码校验 ----
        try:
            # 校验主要编码
            primary_code = coding_data.get("primary_icd10", {}).get("code", "")
            if primary_code:
                validated = lookup_icd10(primary_code)
                if validated:
                    coding_data["primary_icd10"]["description"] = validated.get("description", coding_data["primary_icd10"].get("description", ""))
                    coding_data["primary_icd10"]["confidence"] = max(coding_data["primary_icd10"].get("confidence", 0.8), 0.9)
                    logger.info("coding_agent.primary_code_validated", code=primary_code)
                else:
                    # 编码不存在，回退到文本搜索
                    disease_name = diagnosis.get("primary_diagnosis", {}).get("disease_name", "")
                    search_results = search_icd10_by_text(disease_name or primary_code)
                    if search_results:
                        fallback = search_results[0]
                        coding_data["primary_icd10"]["code"] = fallback.get("code", primary_code)
                        coding_data["primary_icd10"]["description"] = fallback.get("description", "")
                        coding_data["primary_icd10"]["confidence"] = min(coding_data["primary_icd10"].get("confidence", 0.7), 0.75)
                        logger.info("coding_agent.primary_code_fallback", original=primary_code, fallback=fallback["code"])

            # 校验次要编码
            for secondary in coding_data.get("secondary_icd10_codes", []):
                code = secondary.get("code", "")
                if code and not lookup_icd10(code):
                    secondary["confidence"] = min(secondary.get("confidence", 0.7), 0.6)

            # DRG分组确定性查询
            if primary_code:
                drg = get_drg_group(primary_code)
                if drg:
                    coding_data["drg_group"] = {
                        "drg_code": drg.get("drg_code", ""),
                        "description": drg.get("description", ""),
                        "weight": drg.get("weight", 1.0),
                        "mean_los": drg.get("mean_los", 0.0),
                    }
                    logger.info("coding_agent.drg_queried", drg=drg.get("drg_code"))
        except Exception as e:
            logger.warning("coding_agent.validation_fallback", error=str(e))

        logger.info(
            "coding_agent.success",
            primary_code=coding_data.get("primary_icd10", {}).get("code"),
        )
        return {
            "coding_result": coding_data,
            "current_agent": "coding",
        }
    except Exception as e:
        logger.error("coding_agent.error", error=str(e))
        return {
            "coding_result": None,
            "current_agent": "coding",
            "errors": state.errors + [f"编码生成失败: {e}"],
        }
