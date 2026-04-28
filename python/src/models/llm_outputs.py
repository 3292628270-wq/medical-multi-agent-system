"""LLM结构化输出模型 —— 定义每个Agent从LLM中提取数据的schema。

与 domain models (patient.py, diagnosis.py, treatment.py) 的区别：
  - 这里的模型仅包含 LLM 需要输出的字段，不含内部字段 (如 created_at)
  - 使用简单类型 (str 代替 Enum, dict 代替复杂嵌套)，减少 LLM 输出错误
  - 所有必填字段均设默认值，兼容 DeepSeek 等输出不全的情况
"""

from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field, model_validator


# ---- Intake Agent ----

class SymptomOutput(BaseModel):
    name: str = Field(description="症状名称")
    duration_days: int | None = Field(default=None, description="持续时间(天)")
    severity: str = Field(default="moderate", description="严重程度: mild|moderate|severe|critical")
    description: str | None = Field(default=None, description="症状描述")


class AllergyOutput(BaseModel):
    substance: str = Field(description="过敏物质")
    reaction: str | None = Field(default=None, description="过敏反应描述")
    severity: str = Field(default="moderate", description="严重程度")


class MedicationOutput(BaseModel):
    name: str = Field(description="药物名称")
    dosage: str | None = Field(default=None, description="剂量")
    frequency: str | None = Field(default=None, description="用药频率")


class VitalSignsOutput(BaseModel):
    temperature: float | None = Field(default=None, description="体温(℃)")
    heart_rate: int | None = Field(default=None, description="心率(bpm)")
    blood_pressure_systolic: int | None = Field(default=None, description="收缩压")
    blood_pressure_diastolic: int | None = Field(default=None, description="舒张压")
    respiratory_rate: int | None = Field(default=None, description="呼吸频率")
    oxygen_saturation: float | None = Field(default=None, description="血氧饱和度(%)")


class LabResultOutput(BaseModel):
    test_name: str = Field(description="检验项目名称")
    value: str = Field(description="检验结果值")
    unit: str | None = Field(default=None, description="单位")
    reference_range: str | None = Field(default=None, description="参考范围")
    is_abnormal: bool = Field(default=False, description="是否异常")


class IntakeOutput(BaseModel):
    """LLM接诊信息提取结构（所有必填字段均有默认值，兼容LLM输出不全的情况）"""
    name: str = Field(default="未知", description="患者姓名")
    age: int = Field(default=0, ge=0, description="年龄")
    gender: str = Field(default="unknown", description="性别: male|female|other|unknown")
    chief_complaint: str = Field(default="未提供", description="主诉")
    symptoms: list[Any] = Field(default_factory=list, description="症状列表")
    medical_history: list[str] = Field(default_factory=list, description="既往病史")
    family_history: list[str] = Field(default_factory=list, description="家族病史")
    allergies: list[Any] = Field(default_factory=list, description="过敏史")
    current_medications: list[Any] = Field(default_factory=list, description="当前用药")
    vital_signs: Any = Field(default=None, description="生命体征")
    lab_results: list[Any] = Field(default_factory=list, description="实验室检查结果")

    @model_validator(mode="before")
    @classmethod
    def coerce_fields(cls, data: Any) -> Any:
        """将 LLM 可能返回的非预期类型转为安全值。"""
        if not isinstance(data, dict):
            return data
        # 字符串字段：null → 默认值
        for str_field in ("name", "gender", "chief_complaint"):
            if data.get(str_field) is None:
                data[str_field] = "未知" if str_field == "name" else ""
        # list 字段：null → []
        for list_field in ("symptoms", "medical_history", "family_history",
                           "allergies", "current_medications", "lab_results"):
            if data.get(list_field) is None:
                data[list_field] = []
        # vital_signs: 非 dict 时置为 None
        if "vital_signs" in data and not isinstance(data["vital_signs"], dict):
            data["vital_signs"] = None
        # age: 确保为整数
        if "age" in data:
            if isinstance(data["age"], str):
                try:
                    data["age"] = int(data["age"])
                except ValueError:
                    data["age"] = 0
            elif data["age"] is None:
                data["age"] = 0
        return data


# ---- Diagnosis Agent ----

class DiagnosisCandidateOutput(BaseModel):
    disease_name: str = Field(description="疾病名称")
    icd10_hint: str = Field(default="", description="ICD-10编码提示")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度 0-1")
    evidence: list[str] = Field(default_factory=list, description="支持证据")
    reasoning: str = Field(default="", description="推理过程")


class DiagnosisOutput(BaseModel):
    """LLM诊断结果提取结构"""
    primary_diagnosis: DiagnosisCandidateOutput = Field(description="主要诊断")
    differential_list: list[DiagnosisCandidateOutput] = Field(
        default_factory=list, description="鉴别诊断列表"
    )
    recommended_tests: list[str] = Field(default_factory=list, description="建议进一步检查")
    clinical_notes: str = Field(default="", description="临床印象")
    knowledge_sources: list[str] = Field(default_factory=list, description="知识来源")
    needs_more_info: bool = Field(default=False, description="是否需要更多信息")

    @model_validator(mode="before")
    @classmethod
    def coerce_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for list_f in ("differential_list", "recommended_tests", "knowledge_sources"):
            if data.get(list_f) is None:
                data[list_f] = []
        return data


# ---- Treatment Agent ----

class PrescribedMedicationOutput(BaseModel):
    drug_name: str = Field(description="药物名称(商品名)")
    generic_name: str = Field(default="", description="通用名")
    dosage: str = Field(description="剂量")
    route: str = Field(default="oral", description="给药途径: oral|iv|im|topical")
    frequency: str = Field(description="用药频率")
    duration: str = Field(description="用药时长")
    contraindications: list[str] = Field(default_factory=list, description="禁忌症")
    side_effects: list[str] = Field(default_factory=list, description="常见副作用")


class DrugInteractionOutput(BaseModel):
    drug_a: str = Field(description="药物A")
    drug_b: str = Field(description="药物B")
    severity: str = Field(description="严重程度: none|minor|moderate|major|contraindicated")
    description: str = Field(description="相互作用描述")
    recommendation: str = Field(description="建议")


class TreatmentOutput(BaseModel):
    """LLM治疗方案提取结构"""
    diagnosis_addressed: str = Field(default="", description="目标诊断")
    medications: list[PrescribedMedicationOutput] = Field(default_factory=list, description="用药方案")
    drug_interactions: list[DrugInteractionOutput] = Field(
        default_factory=list, description="药物相互作用"
    )
    non_drug_treatments: list[str] = Field(default_factory=list, description="非药物治疗")
    lifestyle_recommendations: list[str] = Field(default_factory=list, description="生活方式建议")
    follow_up_plan: str = Field(default="", description="随访计划")
    warnings: list[str] = Field(default_factory=list, description="重要警告")
    evidence_references: list[str] = Field(default_factory=list, description="循证参考文献")

    @model_validator(mode="before")
    @classmethod
    def coerce_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for list_f in ("medications", "drug_interactions", "non_drug_treatments",
                        "lifestyle_recommendations", "warnings", "evidence_references"):
            if data.get(list_f) is None:
                data[list_f] = []
        return data


# ---- Coding Agent ----

class ICD10CodeOutput(BaseModel):
    code: str = Field(description="ICD-10-CM编码")
    description: str = Field(description="编码描述")
    confidence: float = Field(ge=0.0, le=1.0, description="编码置信度")
    category: str = Field(default="", description="编码类别")


class DRGGroupOutput(BaseModel):
    drg_code: str = Field(description="DRG编码")
    description: str = Field(description="DRG描述")
    weight: float = Field(default=1.0, description="DRG权重")
    mean_los: float = Field(default=0.0, description="平均住院日")


class CodingOutput(BaseModel):
    """LLM编码结果提取结构"""
    primary_icd10: ICD10CodeOutput = Field(description="主要ICD-10编码")
    secondary_icd10_codes: list[ICD10CodeOutput] = Field(
        default_factory=list, description="次要ICD-10编码"
    )
    drg_group: DRGGroupOutput | None = Field(default=None, description="DRG分组")
    coding_notes: str = Field(default="", description="编码说明")
    coding_confidence: float = Field(ge=0.0, le=1.0, default=0.0, description="整体编码置信度")

    @model_validator(mode="before")
    @classmethod
    def coerce_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # drg_group 中的 null 值修复
        if isinstance(data.get("drg_group"), dict):
            dg = data["drg_group"]
            for f in ("weight", "mean_los"):
                if dg.get(f) is None:
                    dg[f] = 0.0
            if dg.get("drg_code") is None:
                dg["drg_code"] = ""
            if dg.get("description") is None:
                dg["description"] = ""
        # confidence null → 0
        if data.get("coding_confidence") is None:
            data["coding_confidence"] = 0.0
        return data
