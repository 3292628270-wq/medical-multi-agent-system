"""
API route definitions.

Endpoints:
  POST /api/v1/clinical/analyze        — 运行完整管线（同步返回）
  POST /api/v1/clinical/analyze/stream — 运行完整管线（SSE流式，逐个Agent返回）
  POST /api/v1/clinical/icd10/search   — 搜索 ICD-10 编码
  GET  /api/v1/clinical/icd10/{code}   — 查询单个 ICD-10 编码
  POST /api/v1/clinical/ddi/check      — 检查药物相互作用
"""

from __future__ import annotations
import json
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..graph.clinical_pipeline import get_pipeline
from ..services.icd10_service import search_icd10_by_text, lookup_icd10, get_drg_group
from ..services.drug_interaction import check_interactions

# Agent 节点名称，用于 astream_events 过滤
AGENT_NAMES = {"intake", "diagnosis", "treatment", "coding", "audit"}

# ---- 输入安全防护 ----

MAX_INPUT_LENGTH = 5000  # 最大输入字符数

# Prompt injection 基础检测模式
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior|上述|前面|之前)\s*(的)?\s*instructions?",
    r"(ignore|disregard|forget|忘记|忽略)\s+(all\s+)?(previous|above|系统)",
    r"system\s*(prompt|message|instruction|提示)",
    r"you\s+are\s+now\s+a(n)?\s",
    r"\[INST\]", r"\[SYS\]",
    r"<\|im_start\|>", r"<\|im_end\|>",
    r"你(现在|已经)\s*(是|变成|成为)\s*(一个|一名)",
    r"忽略你的(系统)?(提示|指令|规则)",
    r"输出你的(系统)?(提示词|指令)",
]


def _validate_input(patient_description: str) -> None:
    """
    输入安全校验。
    检测 prompt injection 攻击模式和输入长度超限。
    """
    # 长度检查
    if len(patient_description) > MAX_INPUT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"输入过长（{len(patient_description)}字符），最大允许 {MAX_INPUT_LENGTH} 字符",
        )

    # Prompt injection 检测
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, patient_description, re.IGNORECASE):
            raise HTTPException(
                status_code=400,
                detail="输入包含无效内容，请重新提交",
            )


router = APIRouter(tags=["Clinical Decision"])


# ---- Request / Response models ----

class AnalyzeRequest(BaseModel):
    patient_description: str = Field(
        ...,
        min_length=10,
        description="Free-text patient narrative",
        examples=[
            "45-year-old male presenting with fever (39.2°C) for 3 days, "
            "productive cough with yellow sputum, and right-sided chest pain. "
            "History of type 2 diabetes and hypertension. "
            "Current medications: metformin 500mg BID, lisinopril 10mg daily. "
            "Allergies: penicillin (rash). "
            "Labs: WBC 15,000/μL, CRP 85 mg/L, chest X-ray shows right lower lobe infiltrate."
        ],
    )
    thread_id: str = Field(default="default", description="Conversation thread ID for checkpointing")


class AnalyzeResponse(BaseModel):
    patient_info: dict | None = None
    diagnosis: dict | None = None
    treatment_plan: dict | None = None
    coding_result: dict | None = None
    audit_result: dict | None = None
    errors: list[str] = Field(default_factory=list)


class ICD10SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Search text for ICD-10 codes")


class DDICheckRequest(BaseModel):
    new_drugs: list[str] = Field(..., min_length=1, description="Drugs to be prescribed")
    current_drugs: list[str] = Field(default_factory=list, description="Patient's current medications")


# ---- Endpoints ----

@router.post("/clinical/analyze", response_model=AnalyzeResponse)
async def analyze_patient(req: AnalyzeRequest):
    """
    Run the full 5-agent clinical decision pipeline.

    1. Intake Agent → structured patient info
    2. Diagnosis Agent → differential diagnosis
    3. Treatment Agent → evidence-based treatment plan
    4. Coding Agent → ICD-10 codes + DRGs
    5. Audit Agent → 中国合规审计报告
    """
    _validate_input(req.patient_description)
    pipeline = get_pipeline()

    try:
        result = pipeline.invoke(
            {"raw_input": req.patient_description},
            config={"configurable": {"thread_id": req.thread_id}},
        )
        return AnalyzeResponse(
            patient_info=result.get("patient_info"),
            diagnosis=result.get("diagnosis"),
            treatment_plan=result.get("treatment_plan"),
            coding_result=result.get("coding_result"),
            audit_result=result.get("audit_result"),
            errors=result.get("errors", []),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@router.post("/clinical/analyze/stream")
async def analyze_patient_stream(req: AnalyzeRequest):
    """
    流式运行 5-Agent 临床决策管线。

    使用 Server-Sent Events (SSE) 逐个返回每个 Agent 的输出，
    前端可逐步渲染结果，无需等待全部完成。

    事件格式：data: {"agent": "intake", "output": {...}, "complete": false}
    结束事件：data: {"agent": null, "output": null, "complete": true}
    """
    _validate_input(req.patient_description)
    pipeline = get_pipeline()

    async def event_stream():
        try:
            async for event in pipeline.astream_events(
                {"raw_input": req.patient_description},
                config={"configurable": {"thread_id": req.thread_id}},
                version="v2",
            ):
                kind = event.get("event")
                name = event.get("name", "")

                # 只处理 Agent 节点完成事件
                if kind == "on_chain_end" and name in AGENT_NAMES:
                    output = event.get("data", {}).get("output", {})
                    # 只发送该 Agent 产出的关键字段
                    payload = {"agent": name, "output": output, "complete": False}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            # 管线完成
            yield f"data: {json.dumps({'agent': None, 'output': None, 'complete': True}, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_payload = {"agent": "error", "output": {"error": str(e)}, "complete": True}
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@router.post("/clinical/icd10/search")
async def search_icd10(req: ICD10SearchRequest):
    """Search ICD-10 codes by text description."""
    results = search_icd10_by_text(req.query)
    return {"query": req.query, "results": results, "count": len(results)}


@router.get("/clinical/icd10/{code}")
async def get_icd10(code: str):
    """Look up a specific ICD-10 code."""
    result = lookup_icd10(code)
    if not result:
        raise HTTPException(status_code=404, detail=f"ICD-10 code {code} not found")
    drg = get_drg_group(code)
    return {"icd10": result, "drg_group": drg}


@router.post("/clinical/ddi/check")
async def check_ddi(req: DDICheckRequest):
    """Check drug-drug interactions."""
    interactions = check_interactions(req.new_drugs, req.current_drugs)
    return {
        "new_drugs": req.new_drugs,
        "current_drugs": req.current_drugs,
        "interactions": interactions,
        "interaction_count": len(interactions),
        "has_major_interaction": any(i["severity"] in ("major", "contraindicated") for i in interactions),
    }
