"""
Treatment Agent — 基于循证医学的治疗方案推荐。

职责：
  - 根据确诊诊断生成治疗方案
  - 先调用药物相互作用服务做确定性DDI检查，再注入LLM做综合判断
  - 校验过敏禁忌症
  - 提供非药物治疗和生活方式建议
"""

from __future__ import annotations
import json
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from ..config.llm import get_structured_llm
from ..models.llm_outputs import TreatmentOutput
from ..services.drug_interaction import check_interactions, check_allergy_contraindication

logger = structlog.get_logger(__name__)

TREATMENT_SYSTEM_PROMPT = """你是一位专家级临床药理学家和治疗专家。根据患者的诊断和临床数据，提供全面的循证治疗方案。

输出JSON格式，包含：
- diagnosis_addressed: 目标诊断
- medications: 用药列表 (drug_name, generic_name, dosage, route, frequency, duration, contraindications, side_effects)
- drug_interactions: 药物相互作用 (drug_a, drug_b, severity, description, recommendation)
- non_drug_treatments: 非药物治疗建议
- lifestyle_recommendations: 生活方式建议
- follow_up_plan: 随访计划
- warnings: 重要警告
- evidence_references: 循证参考来源

规则：
- 优先参考提供的DDI检测结果，也可补充检测库未覆盖的潜在相互作用
- 务必检查过敏史后再推荐药物
- 明确标注严重或禁忌的相互作用
- 至少提供一项非药物治疗方案"""


def treatment_agent(state) -> dict:
    """
    LangGraph 节点：生成治疗方案。
    先做确定性DDI检查，再注入LLM做综合判断。
    读取：state.patient_info, state.diagnosis
    写入：state.treatment_plan, state.current_agent
    """
    logger.info("treatment_agent.start")

    diagnosis = state.diagnosis
    patient_info = state.patient_info

    if not diagnosis:
        return {
            "treatment_plan": None,
            "current_agent": "treatment",
            "errors": state.errors + ["No diagnosis available for treatment planning"],
        }

    # ---- Step 1: 提取当前用药和过敏信息 ----
    current_drug_names = [
        m.get("name", "") for m in patient_info.get("current_medications", [])
    ]
    allergies = [
        a.get("substance", "") for a in patient_info.get("allergies", [])
    ]

    # ---- Step 2: LLM 推理 ----
    structured_llm = get_structured_llm(TreatmentOutput, temperature=0.2)

    context = json.dumps(
        {"patient_info": patient_info, "diagnosis": diagnosis},
        indent=2,
        ensure_ascii=False,
    )

    messages = [
        SystemMessage(content=TREATMENT_SYSTEM_PROMPT),
        HumanMessage(
            content=f"临床数据：\n\n{context}\n\n请给出综合治疗方案。"
        ),
    ]

    try:
        output: TreatmentOutput = structured_llm.invoke(messages)
        treatment_data = output.model_dump(mode="json")

        # ---- Step 3: 确定性DDI检查 ----
        new_drug_names = [
            m.get("generic_name") or m.get("drug_name", "")
            for m in treatment_data.get("medications", [])
        ]

        if new_drug_names:
            try:
                ddi_results = check_interactions(new_drug_names, current_drug_names)
                if ddi_results:
                    # 合并确定性DDI结果到LLM输出中
                    existing_ddis = treatment_data.get("drug_interactions", [])
                    # 去重：避免重复已存在的DDI
                    existing_pairs = {
                        (d.get("drug_a", ""), d.get("drug_b", "")) for d in existing_ddis
                    }
                    for ddi in ddi_results:
                        pair = (ddi["drug_a"], ddi["drug_b"])
                        if pair not in existing_pairs and (pair[1], pair[0]) not in existing_pairs:
                            existing_ddis.append({
                                "drug_a": ddi["drug_a"],
                                "drug_b": ddi["drug_b"],
                                "severity": ddi["severity"],
                                "description": ddi["description"],
                                "recommendation": ddi["recommendation"],
                            })
                    treatment_data["drug_interactions"] = existing_ddis
                    logger.info("treatment_agent.ddi_checked", ddi_count=len(ddi_results))

                    # 过滤禁忌药物
                    contraindicated = {
                        d["drug_a"] for d in ddi_results
                        if d["severity"] in ("contraindicated",)
                    } | {
                        d["drug_b"] for d in ddi_results
                        if d["severity"] in ("contraindicated",)
                    }
                    if contraindicated:
                        treatment_data["warnings"] = treatment_data.get("warnings", []) + [
                            f"禁忌警告：{drug} 存在禁忌相互作用，请勿使用"
                            for drug in contraindicated
                        ]
            except Exception as e:
                logger.warning("treatment_agent.ddi_fallback", error=str(e))

            # Step 4: 过敏检查
            try:
                allergy_warnings = []
                for drug in new_drug_names:
                    result = check_allergy_contraindication(drug, allergies)
                    if result:
                        allergy_warnings.append(
                            f"过敏警告：{result['recommendation']}"
                        )
                if allergy_warnings:
                    treatment_data["warnings"] = treatment_data.get("warnings", []) + allergy_warnings
            except Exception as e:
                logger.warning("treatment_agent.allergy_check_fallback", error=str(e))

        logger.info(
            "treatment_agent.success",
            medications_count=len(treatment_data.get("medications", [])),
        )
        return {
            "treatment_plan": treatment_data,
            "current_agent": "treatment",
        }
    except Exception as e:
        logger.error("treatment_agent.error", error=str(e))
        return {
            "treatment_plan": None,
            "current_agent": "treatment",
            "errors": state.errors + [f"治疗方案生成失败: {e}"],
        }
