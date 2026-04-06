"""
Shared state definition for the clinical decision pipeline.

This is the central data structure that flows through all agents in the
LangGraph pipeline. Each agent reads from and writes to specific fields.
"""

from __future__ import annotations
from typing import Annotated, Any, Optional
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

from ..models.patient import PatientInfo
from ..models.diagnosis import DifferentialDiagnosis
from ..models.treatment import (
    TreatmentPlan,
    CodingResult,
    AuditResult,
)


def _merge_lists(existing: list, new: list) -> list:
    """Reducer that appends new items to existing list."""
    return existing + new


class ClinicalState(BaseModel):
    """
    Pipeline-wide shared state passed between agents.

    Each agent reads what it needs and writes its output fields.
    The LangGraph framework manages state transitions automatically.

    Flow:
        raw_input -> IntakeAgent -> patient_info
        patient_info -> DiagnosisAgent -> diagnosis
        diagnosis -> TreatmentAgent -> treatment_plan
        treatment_plan + diagnosis -> CodingAgent -> coding_result
        everything -> AuditAgent -> audit_result
    """

    # ---- Input ----
    raw_input: str = Field(default="", description="Raw patient description text")

    # ---- Intake Agent output ----
    patient_info: Optional[dict] = Field(
        default=None, description="Structured patient info from IntakeAgent"
    )

    # ---- Diagnosis Agent output ----
    diagnosis: Optional[dict] = Field(
        default=None, description="Differential diagnosis from DiagnosisAgent"
    )
    needs_more_info: bool = Field(
        default=False,
        description="Flag set by DiagnosisAgent when more info is needed",
    )

    # ---- Treatment Agent output ----
    treatment_plan: Optional[dict] = Field(
        default=None, description="Treatment plan from TreatmentAgent"
    )

    # ---- Coding Agent output ----
    coding_result: Optional[dict] = Field(
        default=None, description="ICD-10 / DRGs result from CodingAgent"
    )

    # ---- Audit Agent output ----
    audit_result: Optional[dict] = Field(
        default=None, description="Compliance report from AuditAgent"
    )

    # ---- Shared metadata ----
    messages: Annotated[list[BaseMessage], add_messages] = Field(
        default_factory=list, description="Conversation message history"
    )
    errors: list[str] = Field(
        default_factory=list, description="Errors encountered during pipeline"
    )
    current_agent: str = Field(
        default="", description="Name of the currently executing agent"
    )
