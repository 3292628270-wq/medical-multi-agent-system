# 多Agent医疗临床辅助决策系统 — 优化改造方案

> 基于当前 Python 版 v1.0.0 代码审计，梳理 11 项优化点，按 P0/P1/P2 三级优先级排布。

## 实施进度

| 编号 | 优化项 | 优先级 | 状态 | 完成日期 |
|------|--------|--------|------|----------|
| P0-3 | 诊断循环上限 | P0 | ✅ 已完成 | 2026-04-28 |
| P0-2 | LLM 结构化输出 | P0 | ✅ 已完成 | 2026-04-28 |
| P0-1 | Service 层与 Agent 集成 | P0 | ✅ 已完成 | 2026-04-28 |
| P1-1 | LLM 单例 + Prompt Caching | P1 | ✅ 已完成 | 2026-04-28 |
| P1-2 | SSE 流式输出 | P1 | ✅ 已完成 | 2026-04-28 |
| P1-3 | Agent/Pipeline 测试 | P1 | ✅ 已完成 | 2026-04-28 |
| P2-2 | 知识库扩展（ICD-10/DDI/GraphRAG） | P2 | ✅ 已完成 | 2026-04-28 |
| P2-1 | 持久化 Checkpointer | P2 | ⬜ 待开始 | - |
| P2-3 | 输入安全防护 | P2 | ⬜ 待开始 | - |
| P2-4 | HIPAA 合规实查 | P2 | ⬜ 待开始 | - |

---

---

## 一、当前架构回顾

```
POST /api/v1/clinical/analyze
        │
        ▼
   Intake Agent ──(LLM)──▶ patient_info
        │
        ▼
 Diagnosis Agent ──(LLM)──▶ diagnosis + needs_more_info
        │                        │
        │   needs_more_info=true │
        │   ◀────────────────────┘  (循环：无上限)
        │
        ▼ needs_more_info=false
 Treatment Agent ──(LLM)──▶ treatment_plan
        │
        ▼
  Coding Agent  ──(LLM)──▶ coding_result
        │
        ▼
  Audit Agent   ──(Regex)──▶ audit_result
        │
        ▼
   AnalyzeResponse (同步等待全部完成)
```

**核心问题**：4 个 LLM 智能体完全独立工作，忽略了已有的 Service 层。管道同步串行，无流式输出，无重试，无持久化。

---

## 二、P0（必须修复 — 影响系统正确性）

### P0-1：Service 层与 Agent 层集成 ✅ 已完成 (2026-04-28)

**现状**：`graphrag_service`、`icd10_service`、`drug_interaction_service`、`fhir_service` 四个服务均已实现，但管线中的智能体完全不调用它们。所有诊断推理、用药检查、编码分配都由 LLM "凭空"生成。

**风险**：LLM 幻觉导致错误诊断、错误用药、错误编码，在医疗场景中不可接受。

**改造方案**：

```
当前流程：
  Diagnosis Agent ──(LLM 凭空推理)──▶ 诊断结果

改造后流程：
  Diagnosis Agent
    ├── 1. 提取症状关键词
    ├── 2. graphrag_service.find_diseases_by_symptoms(symptoms)  ← 确定性检索
    ├── 3. 检索结果注入 LLM context 作为参考候选
    └── 4. LLM 基于检索结果 + 患者数据做最终诊断推理

当前流程：
  Treatment Agent ──(LLM 凭空猜测)──▶ 药物 + DDI

改造后流程：
  Treatment Agent
    ├── 1. LLM 生成药物候选
    ├── 2. drug_interaction.check_interactions(new_drugs, current_drugs)  ← 确定性检查
    ├── 3. drug_interaction.check_allergy_contraindication(drug, allergies)
    ├── 4. 检查结果注入 LLM，让 LLM 基于真实 DDI 数据生成最终方案
    └── 5. 过滤掉 contraindicated 的药物

当前流程：
  Coding Agent ──(LLM 凭空猜测)──▶ ICD-10 编码

改造后流程：
  Coding Agent
    ├── 1. LLM 给出 ICD-10 编码建议
    ├── 2. icd10_service.lookup_icd10(code) 验证编码存在性     ← 确定性校验
    ├── 3. 编码不存在 → 用 icd10_service.search_icd10_by_text() 回退搜索
    └── 4. 用 icd10_service.get_drg_group() 获取真实 DRG 权重和住院日
```

**涉及文件**：
- `src/agents/diagnosis_agent.py` — 注入 `graphrag_service`
- `src/agents/treatment_agent.py` — 注入 `drug_interaction`
- `src/agents/coding_agent.py` — 注入 `icd10_service`

**实现步骤**（以 Diagnosis Agent 为例）：

```python
# 改造前（agent 内部直接调 LLM）
def diagnosis_agent(state) -> dict:
    llm = ChatOpenAI(...)
    response = llm.invoke([SystemMessage(...), HumanMessage(...)])
    return {"diagnosis": json.loads(response.content)}

# 改造后（先检索，再推理）
def diagnosis_agent(state) -> dict:
    # 1. 从 symptoms 提取关键词
    symptoms = [s["name"] for s in state.patient_info.get("symptoms", [])]

    # 2. GraphRAG 确定性检索
    rag = get_graphrag_service()
    candidates = rag.find_diseases_by_symptoms(symptoms)

    # 3. 候选疾病注入 prompt
    rag_context = json.dumps(candidates, ensure_ascii=False)
    messages = [
        SystemMessage(DIAGNOSIS_SYSTEM_PROMPT),
        HumanMessage(
            f"Patient:\n{patient_summary}\n\n"
            f"Knowledge Graph matched diseases:\n{rag_context}\n\n"
            f"Use the knowledge graph results as a REFERENCE. Add diseases "
            f"not covered by the graph if clinically warranted."
        ),
    ]
    # 4. LLM 做最终推理
    llm = get_llm()
    response = llm.invoke(messages)
    ...
```

---

### P0-2：LLM 结构化输出 ✅ 已完成 (2026-04-28)（JSON Mode）

**现状**：4 个智能体都用 `llm.invoke()` + `json.loads(response.content)` + 手动剥离 markdown fence。LLM 可能返回非 JSON、缺字段、类型错误、包在 markdown 里的 JSON。

**风险**：这是当前系统最频繁的失败模式。任何一个智能体的 JSON 解析失败，下游都收到 `None`。

**改造方案**：使用 LangChain 的 `with_structured_output()` 方法。

```python
# 改造前
llm = ChatOpenAI(model=..., temperature=0.1)
response = llm.invoke(messages)
content = response.content.strip()
if content.startswith("```"):
    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
data = json.loads(content)

# 改造后
from ..models.patient import PatientInfo

llm = ChatOpenAI(model=..., temperature=0.1)
structured_llm = llm.with_structured_output(PatientInfo, method="json_mode")
patient = structured_llm.invoke(messages)  # 直接返回 Pydantic 对象，自动校验
```

**影响范围**：
- Intake: 绑定 `PatientInfo` 模型
- Diagnosis: 绑定 `DifferentialDiagnosis` 模型（需新增 `needs_more_info` 字段或包装类）
- Treatment: 绑定 `TreatmentPlan` 模型
- Coding: 绑定 `CodingResult` 模型

**注意事项**：
- `json_mode` 要求 `gpt-4o-mini` 及以上模型，当前模型满足
- 必须要求 LLM 返回符合 Pydantic schema 的 JSON，不再需要手动剥离 markdown

---

### P0-3：诊断循环上限 ✅ 已完成 (2026-04-28)

**现状**：`_route_after_diagnosis` 依赖 `state.needs_more_info` 布尔值决定是否循环回 Intake。没有计数器，LLM 可能持续返回 `true`，导致无限循环消耗 token 和 API 费用。

**改造方案**：

```python
# state.py 新增字段
class ClinicalState(BaseModel):
    ...
    diagnosis_retry_count: int = 0  # 新增：诊断循环计数

# clinical_pipeline.py 路由函数改造
MAX_DIAGNOSIS_RETRIES = 3

def _route_after_diagnosis(state: ClinicalState) -> str:
    if state.needs_more_info and state.diagnosis_retry_count < MAX_DIAGNOSIS_RETRIES:
        return "intake"
    # 超过上限或信息足够 → 强制进入 treatment
    return "treatment"

# intake_agent.py 中递增计数（第二次进入时）
def intake_agent(state) -> dict:
    ...
    return {
        "patient_info": patient_dict,
        "current_agent": "intake",
        "diagnosis_retry_count": state.diagnosis_retry_count + 1,
    }
```

---

## 三、P1（应该尽快做 — 影响系统可用性和开发效率）

### P1-1：LLM 单例 + Prompt Caching + 连接复用 ✅ 已完成 (2026-04-28)

**现状**：5 个智能体各自独立创建 `ChatOpenAI(...)` 实例。每次调用重新发送相同的 system prompt（最长约 1000 token）。

**改造方案**：

```python
# src/config/llm.py (新建)
from functools import lru_cache
from langchain_openai import ChatOpenAI
from langchain_core.caches import InMemoryCache
from .settings import get_settings

@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.2) -> ChatOpenAI:
    """全局 LLM 单例，复用 HTTP 连接，支持 prompt caching。"""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=temperature,
        model_kwargs={
            # OpenAI prompt caching: 自动缓存 >1024 token 的前缀
            # system prompt 会被缓存，后续请求只发送增量内容
        },
    )

# 各 agent 改造
# 改造前
llm = ChatOpenAI(model=settings.openai_model, api_key=..., temperature=0.1)

# 改造后
from ..config.llm import get_llm
llm = get_llm(temperature=0.1)  # 或者结构化版本，也统一创建
```

**预期收益**：
- Prompt caching：system prompt 仅首次传输，后续请求节省 50-70% input token
- 连接复用：减少 TCP/TLS 握手开销

---

### P1-2：流式输出（SSE） ✅ 已完成 (2026-04-28)

**现状**：`pipeline.invoke()` 同步执行完毕才返回完整 `AnalyzeResponse`。用户等待 15-30 秒看到的是白屏/loading。

**改造方案**：

```python
# routes.py 新增流式端点
from fastapi.responses import StreamingResponse
import json

@router.post("/clinical/analyze/stream")
async def analyze_patient_stream(req: AnalyzeRequest):
    """流式返回每个 Agent 的输出，前端可逐阶段渲染。"""

    async def event_stream():
        pipeline = get_pipeline()

        # 使用 astream_events 获取每个节点完成事件
        async for event in pipeline.astream_events(
            {"raw_input": req.patient_description},
            config={"configurable": {"thread_id": req.thread_id}},
            version="v2",
        ):
            kind = event.get("event")
            if kind == "on_chain_end" and event.get("name") in AGENT_NAMES:
                agent_name = event["name"]
                output = event["data"].get("output", {})
                yield f"data: {json.dumps({'agent': agent_name, 'output': output})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

**前端使用**：
```javascript
const eventSource = new EventSource('/api/v1/clinical/analyze/stream');
eventSource.onmessage = (e) => {
  const { agent, output } = JSON.parse(e.data);
  // 逐步渲染每个 Agent 的结果：Intake → Diagnosis → Treatment → ...
};
```

**注意**：流式端点需要保留原有同步端点以保持向后兼容。

---

### P1-3：Agent 层与管线层测试 ✅ 已完成 (2026-04-28)

**现状**：29 个测试全部针对 Service 层。Agent 和 Pipeline 没有任何测试。

**改造方案**：

| 测试层级 | 测试内容 | 方式 |
|----------|----------|------|
| Agent 单元测试 | JSON 解析逻辑、错误处理路径 | Mock `ChatOpenAI` |
| Agent 单元测试 | Service 注入后的检索逻辑 | Mock Service 返回值 |
| Pipeline 集成测试 | 条件路由（正常路径 / 循环 / 超限） | Mock 所有 LLM 调用 |
| Pipeline 集成测试 | State 合并正确性 | Mock 所有 LLM 调用 |

```python
# tests/test_agents.py (新建)
class TestIntakeAgent:
    def test_parse_valid_json(self, mock_llm):
        mock_llm.invoke.return_value.content = '{"name": "Test", "age": 45, ...}'
        result = intake_agent(state_with_raw_input)
        assert result["patient_info"]["name"] == "Test"
        assert result["errors"] is None

    def test_parse_invalid_json(self, mock_llm):
        mock_llm.invoke.return_value.content = 'not json'
        result = intake_agent(state_with_raw_input)
        assert result["patient_info"] is None
        assert len(result["errors"]) > 0

    def test_empty_input(self):
        result = intake_agent(state_with_empty_raw_input)
        assert "No raw input" in result["errors"][0]


class TestClinicalPipeline:
    def test_full_pipeline_normal_flow(self):
        """模拟正常流程：Intake → Diagnosis → Treatment → Coding → Audit"""
        ...

    def test_pipeline_loop_back(self):
        """needs_more_info=true 时回退到 Intake"""
        ...

    def test_pipeline_loop_limit(self):
        """超过 3 次循环后强制进入 Treatment"""
        ...
```

---

## 四、P2（生产化前提 — 成本优化与合规深化）

### P2-1：持久化 Checkpointer

**现状**：`MemorySaver()` 将所有状态存于内存。进程重启 = 所有会话丢失。

**改造方案**：

```python
# clinical_pipeline.py
from langgraph.checkpoint.postgres import PostgresSaver

def build_clinical_pipeline(checkpointer=None):
    ...
    if checkpointer is None:
        settings = get_settings()
        checkpointer = PostgresSaver.from_conn_string(
            f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )
    return workflow.compile(checkpointer=checkpointer)
```

PostgresSaver 已在 docker-compose 中有现成的 PostgreSQL 服务，只需替换即可。

---

### P2-2：知识库扩展

**现状**：DDI 数据库仅 10 条，症状映射仅 11 种，ICD-10 仅 30 条，疾病映射仅 15 条。覆盖范围不足以支撑真实临床场景。

**改造方案**（按优先级排序）：

| 知识库 | 当前规模 | 目标规模 | 数据源 |
|--------|----------|----------|--------|
| 药物相互作用 | 10 条 | 10,000+ 条 | [OpenFDA Drug API](https://open.fda.gov/) 或 RxNorm |
| ICD-10-CM 编码 | ~30 条 | 完整 70,000+ | CMS 公开数据 / WHO ICD-10 |
| 症状-疾病映射 | 11 种症状 | UMLS 级别 | UMLS Metathesaurus (需授权) 或 DOID |
| DRG 分组 | 9 组 | 完整 MS-DRG | CMS MS-DRG 定义表 |

短期策略：用 OpenFDA API 替代硬编码数据库，不引入重型依赖。

```python
# src/services/drug_interaction.py
async def check_interactions_remote(new_drugs: list[str], current_drugs: list[str]):
    """通过 OpenFDA API 实时查询 DDI，替代本地硬编码数据库。"""
    import httpx
    async with httpx.AsyncClient() as client:
        for drug in new_drugs:
            resp = await client.get(
                "https://api.fda.gov/drug/event.json",
                params={"search": f"patient.drug.medicinalproduct:{drug}", "limit": 10}
            )
            ...
```

---

### P2-3：输入安全防护

**现状**：`AnalyzeRequest.patient_description` 仅校验 `min_length=10`。存在 prompt injection 风险和敏感信息未前置检测的问题。

**改造方案**：

```python
# src/api/middleware.py (新建) 或 routes.py 中增加前置校验

import re

# 1. Prompt injection 基础防护
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions?",
    r"system\s*(prompt|message|instruction)",
    r"you\s+are\s+now\s+a(n)?\s",
    r"\[INST\]", r"\[SYS\]",  # 其他 LLM 框架的标记
]

def check_prompt_injection(text: str) -> bool:
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

# 2. 输入字符数上限（防止 token 消耗攻击）
MAX_INPUT_LENGTH = 5000

# 3. routes.py 中集成
@router.post("/clinical/analyze", response_model=AnalyzeResponse)
async def analyze_patient(req: AnalyzeRequest):
    if check_prompt_injection(req.patient_description):
        raise HTTPException(status_code=400, detail="Invalid input detected")
    if len(req.patient_description) > MAX_INPUT_LENGTH:
        raise HTTPException(status_code=400, detail="Input too long")
    ...
```

---

### P2-4：HIPAA 合规检查从"假检查"变为"实查"

**现状**：Audit Agent 的结构性检查全部硬编码 `True`（`data_encryption_at_rest: True` 等），从不验证实际系统状态。PHI 扫描正则过于粗糙——IP 地址正则会误匹配血常规数值如 `15,000`。

**改造方案**：

1. **PHI 扫描优化**

```python
# 问题：\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b 会误匹配类似 IP 的数字
# 修复：增加上下文约束（排除医疗数据中常见的数字模式）

PHI_PATTERNS = {
    "ip_address": r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?!\d|[./]\d)",
    # 更精确的 IP 匹配，排除 0.0.0.0 这类占位符
    "ssn": r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)",
    "mrn": r"\bMRN[:\s]?\d{6,10}\b",  # 更精确的 MRN 格式
    "zip_code": r"(?<!\d)\d{5}(?:-\d{4})?(?!\d)",
    ...
}
```

2. **结构性检查接入真实系统状态**

```python
# 不再硬编码 True，而是检查配置和运行状态
structural_checks = {
    "data_encryption_at_rest": _check_db_tls_enabled(),
    "data_encryption_in_transit": _check_https_enabled(),
    "access_control_rbac": _check_rbac_configured(),
    "audit_logging": _verify_audit_log_writable(),
    ...
}
```

---

## 五、实施路线图

```
Week 1-2: P0 修复
  ├── Day 1-3: P0-2 结构化输出 (4 个 Agent 全部改造)
  ├── Day 4-6: P0-1 Service 集成 (Diagnosis + Treatment + Coding)
  ├── Day 7-8: P0-3 循环上限 + P0 测试
  └── Day 9-10: 全链路回归测试

Week 3-4: P1 改进
  ├── Day 1-2: P1-1 LLM 单例 + Prompt Caching
  ├── Day 3-4: P1-2 流式输出
  ├── Day 5-7: P1-3 Agent + Pipeline 测试
  └── Day 8-10: 文档更新 + 端到端验证

Month 2: P2 生产化
  ├── Week 1: P2-1 PostgresSaver + P2-4 HIPAA 实查
  ├── Week 2: P2-2 知识库接入 OpenFDA
  ├── Week 3: P2-3 输入安全防护
  └── Week 4: 压力测试 + 性能调优 + 部署文档
```

---

## 六、风险与注意事项

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| JSON mode 迁移导致 LLM 返回格式不兼容 | Agent 输出全部失败 | 保留 `json.loads` 作为 fallback，双路径运行一段时间 |
| Service 注入后 token 消耗增加 | API 费用上升 | prompt caching + 精简注入格式 |
| 流式输出破坏 LangGraph checkpoint 时序 | 会话状态不一致 | 流式端点与同步端点分离，流式不写 checkpoint |
| OpenFDA API 不可用 | DDI 检查降级 | 保留本地硬编码数据库作为 fallback |
| PostgresSaver 迁移丢失现有 checkpoints | 会话中断 | 迁移前导出 MemorySaver 数据，或并行运行两套 |
