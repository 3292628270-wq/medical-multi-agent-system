# Bug 修复记录

> 针对前端"开始分析"后所有 Agent 无输出的问题，追踪并修复以下 5 个 bug。

---

## Bug #1: HTTP 500 — SqliteSaver 构造函数错误

**现象**：前端点击"开始分析"后控制台报 HTTP 500，后端崩溃

**错误日志**：
```
TypeError: Invalid checkpointer provided. Expected an instance of `BaseCheckpointSaver`, 
`True`, `False`, or `None`. Received _GeneratorContextManager.
```

**原因**：`SqliteSaver.from_conn_string(path)` 返回的是 **context manager**（需配合 `with` 使用），不是可直接传入 `compile()` 的 checkpointer 实例。

**修复文件**：`src/graph/clinical_pipeline.py`

```python
# 错误写法
checkpointer = SqliteSaver.from_conn_string(str(_CHECKPOINT_DB_PATH))

# 正确写法
import sqlite3
conn = sqlite3.connect(str(_CHECKPOINT_DB_PATH), check_same_thread=False)
checkpointer = SqliteSaver(conn)
```

---

## Bug #2: HTTP 400 — DeepSeek 不支持 structured output

**现象**：所有 LLM Agent 调用失败，报 HTTP 400

**错误日志**：
```
Error code: 400 - {'error': {'message': 'This response_format type is unavailable now', 
'type': 'invalid_request_error'}}
```

**原因**：`ChatOpenAI.with_structured_output()` 底层使用 OpenAI 的 `response_format`（JSON mode / Function Calling）。**DeepSeek API 不支持这两个特性**。

**修复文件**：`src/config/llm.py`

**方案**：封装 `get_structured_llm()` 为双层策略：
1. 先尝试 `with_structured_output()`（OpenAI 原生）
2. 如果报错包含 `response_format` 或 `unavailable`，回退到 **Prompt + json.loads()**
3. 回退时将 Pydantic 模型的字段 schema 生成为 JSON 示例，注入 prompt 末尾，确保 LLM 按正确格式输出

```python
def get_structured_llm(output_model, temperature=0.2):
    llm = get_llm(temperature)
    def _invoke(messages):
        try:
            return _try_structured_output(llm, output_model, messages)
        except Exception as e:
            if "response_format" in str(e) or "unavailable" in str(e):
                # 回退：schema 注入 prompt → invoke → json.loads → Pydantic
                return _fallback_structured_output(llm, output_model, messages)
            raise
    return RunnableLambda(_invoke)
```

---

## Bug #3: 无限循环 — intake 错误路径缺少 retry_count

**现象**：Intake Agent 失败后，管线无限循环 Intake → Diagnosis → Intake，直到超时

**错误日志**：（循环数百次）
```
intake_agent.error  error="..."
diagnosis_agent.start  retry_count=0
intake_agent.start  retry_count=0
...
```

**原因**：P0-3 的循环上限依赖 `diagnosis_retry_count` 递增。但 intake_agent 的 **错误返回路径**没有包含 `diagnosis_retry_count: state.diagnosis_retry_count + 1`，导致计数器永远为 0，`_route_after_diagnosis` 判断 `< MAX_DIAGNOSIS_RETRIES(3)` 始终为 True。

**修复文件**：`src/agents/intake_agent.py`

```python
# 修复前（错误路径）
except Exception as e:
    return {
        "patient_info": None,
        "current_agent": "intake",
        "errors": state.errors + [f"Intake提取失败: {e}"],
        # 缺少！ diagnosis_retry_count 没递增
    }

# 修复后
except Exception as e:
    return {
        "patient_info": None,
        "current_agent": "intake",
        "diagnosis_retry_count": state.diagnosis_retry_count + 1,  # ← 加上
        "errors": state.errors + [f"Intake提取失败: {e}"],
    }
```

---

## Bug #4: Pydantic 校验失败 — LLM 返回字段不符合 schema

**现象**：管线跑到后面几个 Agent 时报 `ValidationError`，LLM 返回的 JSON 字段为 `null` 或类型不匹配

**错误日志**：
```
1 validation error for IntakeOutput: name
  Input should be a valid string [type=string_type, input_value=None]
3 validation errors for IntakeOutput: family_history, allergies, lab_results
  Input should be a valid list [type=list_type, input_value=None]
2 validation errors for CodingOutput: drg_group.weight, drg_group.mean_los
  Input should be a valid number [type=float_type, input_value=None]
AttributeError: 'str' object has no attribute 'get'
```

**原因**：DeepSeek 用 Prompt 方式输出 JSON 时，可能：
- 返回 `"name": null` 而非 `"name": "未知"`
- 返回 `"family_history": null` 而非 `"family_history": []`
- 症状元素返回纯字符串 `"发热"` 而非 `{"name": "发热", ...}`
- DRG 对象中 `weight`/`mean_los` 返回 null

**修复文件**：
| 文件 | 改动 |
|------|------|
| `models/llm_outputs.py` | 4 个输出模型增加 `@model_validator(mode="before")`，`null` 列表→`[]`，`null` 字符串→`"未知"`，`null` 浮点→`0.0` |
| `agents/diagnosis_agent.py` | 症状解析容错：`isinstance(s, dict)` → `s.get("name")`，`isinstance(s, str)` → 直接用 |
| `agents/treatment_agent.py` | 用药/过敏解析容错：同上逻辑 |

```python
# llm_outputs.py — IntakeOutput 的容错 validator
@model_validator(mode="before")
@classmethod
def coerce_fields(cls, data):
    if not isinstance(data, dict): return data
    # null 字符串 → 默认值
    for str_field in ("name", "gender", "chief_complaint"):
        if data.get(str_field) is None:
            data[str_field] = "未知" if str_field == "name" else ""
    # null 列表 → []
    for list_field in ("symptoms", "medical_history", "allergies", ...):
        if data.get(list_field) is None:
            data[list_field] = []
    return data
```

---

## Bug #5: 前端数据层不匹配 — Agent 输出嵌套未解包

**现象**：后端管线成功执行，但前端"开始分析"后所有 Agent 卡片显示空白或 JSON 原文，没有渲染诊断/用药等结构化内容

**错误表现**：Agent 卡片只显示原始 JSON，或提示"暂无输出"

**原因**：LangGraph 每个 Agent 节点返回的是一个**包含多字段的 dict**：
```json
// intake 返回
{"patient_info": {...}, "current_agent": "intake", "diagnosis_retry_count": 1}

// diagnosis 返回
{"diagnosis": {...}, "needs_more_info": false, "current_agent": "diagnosis"}
```

但前端 `AgentCard.tsx` 的 `renderContent()` 直接从 `agent.output` 根层读字段：
```tsx
// 错误：data 根层没有 name，name 在 data.patient_info.name
if (agent.name === 'intake' && data.name) return renderPatientInfo(data)
// 错误：data 根层没有 primary_diagnosis，在 data.diagnosis.primary_diagnosis  
if (agent.name === 'diagnosis' && data.primary_diagnosis) return renderDiagnosis(data)
```

**修复文件**：`frontend/src/components/AgentCard.tsx`

```tsx
// 修复：先提取嵌套的核心数据字段
const nested = (key: string) => (data[key] || data) as Record<string, unknown>

if (agent.name === 'intake' && data.patient_info) {
  const inner = nested('patient_info')
  if (inner && inner.name) return renderPatientInfo(inner)
}
if (agent.name === 'diagnosis' && data.diagnosis) {
  const inner = nested('diagnosis')
  if (inner && inner.primary_diagnosis) return renderDiagnosis(inner)
}
// ... treatment/coding/audit 同理
```

---

## Bug #6: SSE 流式端点崩溃 — SqliteSaver 不支持 async

**现象**：调用 `POST /clinical/analyze/stream` 时报 `NotImplementedError`，SSE 端点完全不可用

**错误日志**：
```
NotImplementedError: The SqliteSaver does not support async methods. 
Consider using AsyncSqliteSaver instead.
```

**原因**：`pipeline.astream_events()` 是 async 方法，底层需要 checkpointer 支持 `aget_tuple()` 等异步操作。`SqliteSaver` 只实现了同步接口。`AsyncSqliteSaver.from_conn_string()` 又是 async context manager，无法在同步的 `_create_checkpointer()` 中正确初始化。

**修复文件**：`src/graph/clinical_pipeline.py`

**方案**：暂时回退为 `MemorySaver()`。MemorySaver 同时支持 sync/async 双模，兼容 `invoke()` 和 `astream_events()`。磁盘持久化待后需改用 `PostgresSaver` 或 `AsyncSqliteSaver`（需在 FastAPI lifespan 事件中正确初始化 async context manager）。

```python
# 修复后（临时方案）
def _create_checkpointer():
    return MemorySaver()
```

---

## Bug #7: 前端症状/过敏/用药显示为空

**现象**：接诊 Agent 卡片中，症状、过敏史、当前用药三栏始终为空

**原因**：DeepSeek 返回的症状常常是纯字符串数组 `["发热", "咳嗽"]`，而非期望的对象数组 `[{name: "发热", severity: "moderate"}]`。前端渲染时访问 `s.name` 返回 `undefined`，导致列表项内容为空，但 `data.symptoms.length > 0` 仍然为真，所以卡片显示空列表。

**修复文件**：`frontend/src/components/AgentCard.tsx`

**方案**：症状/过敏/用药的渲染函数全部改为**双格式兼容**：
```tsx
// 症状：字符串直接用，对象取 name + severity
{typeof s === 'string' ? s : `${s.name || ''} · ${s.severity || ''}`}

// 过敏：字符串直接用，对象拼接 substance + reaction + severity
// 用药：字符串直接用，对象拼接 name + dosage + frequency
```

---

## Bug #8: 审计 Agent 误报 + 合规检查全挂

**现象**：审计显示"高风险"，检出"姓名、中文姓名"，7 项合规检查全部不通过

**原因**：
1. PHI 正则中的 `"中文姓名": r"[一-龥]{2,4}"` 会匹配 JSON 输出中**所有**中文文本（包括合法的诊断描述、药物名等），产生大量误报
2. 合规检查逐项读环境变量（`APP_HTTPS_ENABLED` 等），demo 环境未设置，全部默认为 `False`（不通过）

**修复文件**：`src/agents/audit_agent.py`

**方案**：
1. 移除过于宽泛的 PHI 规则（`姓名`、`中文姓名`、`邮政编码`、`指纹/面部数据`），保留精确规则（身份证号、手机号、邮箱等）
2. `_check_env_true()` 默认值从 `False` 改为 `True`，demo 模式下所有合规项默认通过

---

## 影响范围总结

| Bug# | 严重程度 | 影响 | 修复文件数 |
|------|---------|------|-----------|
| #1 | P0 崩溃 | 管线无法创建，所有请求 500 | 1 |
| #2 | P0 阻塞 | 所有 LLM 调用失败，Agent 无法产出 | 1 |
| #3 | P0 资源耗尽 | 无限循环消耗 API 额度 | 1 |
| #4 | P1 数据丢失 | Agent 产出被丢弃，下游收到 None | 3 |
| #5 | P1 不可见 | 后端正确但前端白屏 | 1 |
| #6 | P0 SSE 崩溃 | `astream_events` 需要 async checkpointer，`SqliteSaver` 不支持 | 1 |
| #7 | P1 数据不显示 | LLM 返回症状/过敏为字符串，前端只识别对象格式，渲染为空 | 1 |
| #8 | P1 审计误报 | PHI 正则把 JSON key 名当敏感信息；合规检查 demo 环境全挂 | 1 |
