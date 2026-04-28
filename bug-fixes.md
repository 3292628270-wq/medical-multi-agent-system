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

## 影响范围总结

| Bug# | 严重程度 | 影响 | 修复文件数 |
|------|---------|------|-----------|
| #1 | P0 崩溃 | 管线无法创建，所有请求 500 | 1 |
| #2 | P0 阻塞 | 所有 LLM 调用失败，Agent 无法产出 | 1 |
| #3 | P0 资源耗尽 | 无限循环消耗 API 额度 | 1 |
| #4 | P1 数据丢失 | Agent 产出被丢弃，下游收到 None | 3 |
| #5 | P1 不可见 | 后端正确但前端白屏 | 1 |
