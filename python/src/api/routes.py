"""
API route definitions.

Endpoints:
  POST /api/v1/clinical/analyze   — Run full pipeline on raw patient text
  POST /api/v1/clinical/intake    — Run intake agent only
  GET  /api/v1/clinical/icd10     — Search ICD-10 codes
  GET  /api/v1/clinical/ddi       — Check drug interactions
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..graph.clinical_pipeline import get_pipeline
from ..services.icd10_service import search_icd10_by_text, lookup_icd10, get_drg_group
from ..services.drug_interaction import check_interactions

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
    5. Audit Agent → HIPAA compliance report
    """
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
