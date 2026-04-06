"""
LangGraph clinical decision pipeline orchestrator.

Wires the five agents into a sequential pipeline with conditional routing:

    Intake -> Diagnosis --(needs_more_info?)--> Intake (loop back)
                       \--(ready)-----------> Treatment -> Coding -> Audit -> END
"""

from __future__ import annotations
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import ClinicalState
from ..agents.intake_agent import intake_agent
from ..agents.diagnosis_agent import diagnosis_agent
from ..agents.treatment_agent import treatment_agent
from ..agents.coding_agent import coding_agent
from ..agents.audit_agent import audit_agent


def _route_after_diagnosis(state: ClinicalState) -> str:
    """
    Conditional edge after Diagnosis Agent.
    If the agent determines more patient info is needed, route back to Intake.
    Otherwise proceed to Treatment.
    """
    if state.needs_more_info:
        return "intake"
    return "treatment"


def build_clinical_pipeline(checkpointer=None):
    """
    Construct and compile the clinical decision LangGraph pipeline.

    Returns a compiled graph that can be invoked with:
        result = pipeline.invoke({"raw_input": "patient description ..."})
    """
    workflow = StateGraph(ClinicalState)

    # --- Register nodes ---
    workflow.add_node("intake", intake_agent)
    workflow.add_node("diagnosis", diagnosis_agent)
    workflow.add_node("treatment", treatment_agent)
    workflow.add_node("coding", coding_agent)
    workflow.add_node("audit", audit_agent)

    # --- Define edges ---
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "diagnosis")

    workflow.add_conditional_edges(
        "diagnosis",
        _route_after_diagnosis,
        {
            "intake": "intake",
            "treatment": "treatment",
        },
    )

    workflow.add_edge("treatment", "coding")
    workflow.add_edge("coding", "audit")
    workflow.add_edge("audit", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)


# Convenience singleton
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_clinical_pipeline()
    return _pipeline
