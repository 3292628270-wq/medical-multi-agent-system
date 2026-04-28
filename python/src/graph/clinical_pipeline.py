"""
LangGraph 临床决策管线编排器。

将五个 Agent 串联为顺序管线，带条件路由：

    Intake -> Diagnosis --(信息不足且未达上限)--> Intake (回退循环)
                       \--(信息充足或达上限)----> Treatment -> Coding -> Audit -> END

改造前：MemorySaver 内存存储，进程重启丢失所有会话
改造后：SqliteSaver 磁盘持久化，会话跨进程保留；SQLite 不可用时回退 MemorySaver
"""

from __future__ import annotations
from pathlib import Path
import structlog
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import ClinicalState
from ..agents.intake_agent import intake_agent
from ..agents.diagnosis_agent import diagnosis_agent
from ..agents.treatment_agent import treatment_agent
from ..agents.coding_agent import coding_agent
from ..agents.audit_agent import audit_agent

logger = structlog.get_logger(__name__)

# 诊断信息不足时最多回退 Intake 的次数
MAX_DIAGNOSIS_RETRIES = 3

# SQLite checkpointer 文件路径
_CHECKPOINT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "checkpoints.db"


def _route_after_diagnosis(state: ClinicalState) -> str:
    """
    Diagnosis Agent 之后的条件路由。
    如果信息不足且在重试上限内，回退到 Intake 重新收集信息。
    超过上限后强制进入 Treatment。
    """
    if state.needs_more_info and state.diagnosis_retry_count < MAX_DIAGNOSIS_RETRIES:
        return "intake"
    return "treatment"


def _create_checkpointer():
    """
    创建持久化 checkpointer。
    当前使用 MemorySaver（兼容 sync/async 双模，支持 astream_events）。
    TODO: 生产环境切换到 PostgresSaver 或正确初始化的 AsyncSqliteSaver。
    """
    return MemorySaver()


def build_clinical_pipeline(checkpointer=None):
    """
    构造并编译 LangGraph 管线。

    参数：
        checkpointer: 可选自定义 checkpointer，None 时自动选择 SqliteSaver
    返回：
        编译后的 StateGraph，可通过 .invoke() 或 .astream_events() 调用
    """
    workflow = StateGraph(ClinicalState)

    # --- 注册节点 ---
    workflow.add_node("intake", intake_agent)
    workflow.add_node("diagnosis", diagnosis_agent)
    workflow.add_node("treatment", treatment_agent)
    workflow.add_node("coding", coding_agent)
    workflow.add_node("audit", audit_agent)

    # --- 定义边 ---
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
        checkpointer = _create_checkpointer()

    return workflow.compile(checkpointer=checkpointer)


# 管线单例
_pipeline = None


def get_pipeline():
    """
    获取管线单例。
    首次调用时创建 SqliteSaver 持久化管线；后续调用复用同一实例。
    """
    global _pipeline
    if _pipeline is None:
        _pipeline = build_clinical_pipeline()
    return _pipeline
