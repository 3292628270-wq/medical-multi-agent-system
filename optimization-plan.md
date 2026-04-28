# 多Agent医疗临床辅助决策系统 — 优化改造方案

> 基于 Python 版 v1.0.0 代码审计，共 10 项优化，P0/P1/P2 三级，**已全部完成**。

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
| P2-4 | HIPAA → 中国数据合规审计 | P2 | ✅ 已完成 | 2026-04-28 |
| P2-1 | 持久化 Checkpointer | P2 | ✅ 已完成 | 2026-04-28 |
| P2-3 | 输入安全防护 | P2 | ✅ 已完成 | 2026-04-28 |

---

## 一、架构总览

### 改造前

```
POST /api/v1/clinical/analyze
        │
        ▼
   Intake Agent ──(LLM 手解 JSON)──▶ patient_info
        │
        ▼
 Diagnosis Agent ──(LLM 凭空诊断)──▶ diagnosis
        │
        │   needs_more_info=true → 无上限循环
        │
        ▼
 Treatment Agent ──(LLM 凭空开药)──▶ treatment_plan
        │
        ▼
  Coding Agent  ──(LLM 凭空编码)──▶ coding_result
        │
        ▼
  Audit Agent   ──(HIPAA 假检查)──▶ audit_result
        │
        ▼
  AnalyzeResponse (同步等待 15-30s)

核心问题：
- 4 个 LLM Agent 不调用已有的 Service 层，全靠幻觉
- 手写 json.loads() 解析，无 schema 校验
- 无循环上限、无持久化、无流式输出
- ICD-10 30 条 / DDI 10 条 / GraphRAG 11 症状
- HIPAA 合规检查全部硬编码 True
- 0 个 Agent/Pipeline 测试
```

### 改造后

```
POST /api/v1/clinical/analyze         POST /api/v1/clinical/analyze/stream
        │                                      │
        ▼                                      ▼
  ┌─ 输入安全防护 ──────────────────────┐   SSE 流式逐个返回
  │ prompt injection 检测 + 长度限制     │
  └──────────────────────────────────────┘
        │
        ▼
   Intake ──(structured_output→IntakeOutput)──▶ patient_info
        │
        ▼
 Diagnosis ──(GraphRAG检索→LLM推理)──▶ diagnosis + needs_more_info
        │                                      │
        │   回退循环（上限3次）                  │
        │                                      │
        ▼                                      │
 Treatment ──(LLM→DDI确定性检查→合并)──▶ treatment_plan
        │
        ▼
  Coding ──(LLM→ICD-10 SQLite校验)──▶ coding_result
        │
        ▼
  Audit ──(PIPL/数据安全法审查)──▶ audit_result
        │
        ▼
   SqliteSaver 持久化 + 30 个测试覆盖
```

---

## 二、P0 — 正确性修复

### P0-3：诊断循环上限

| 改造前 | 改造后 |
|--------|--------|
| `needs_more_info=true` 时无限循环回退 Intake | `diagnosis_retry_count` 计数器，上限 3 次后强制进入 Treatment |
| 状态模型无循环计数字段 | `ClinicalState` 新增 `diagnosis_retry_count: int = 0` |
| 每次循环消耗 2 次 LLM 调用，无上限 | 最多 3 次循环 = 最多 6 次额外 LLM 调用 |

**改动文件**：`state.py`（+1 字段）、`clinical_pipeline.py`（+`MAX_DIAGNOSIS_RETRIES=3`）、`intake_agent.py`（+递增逻辑）

---

### P0-2：LLM 结构化输出

| 改造前 | 改造后 |
|--------|--------|
| `llm.invoke()` → `response.content.strip()` → 手动剥离 markdown fence → `json.loads()` | `llm.with_structured_output(PydanticModel)` → 直接返回校验后的 Pydantic 对象 |
| JSON 解析失败 → 整个 Agent 输出 `None` | LLM 按 schema 输出，自动校验，几乎零解析失败 |
| 4 个 Agent 各自手写 JSON schema 到 SystemPrompt | 新增 `models/llm_outputs.py`，5 个结构化输出模型（Intake/Diagnosis/Treatment/Coding） |

```python
# 改造前
llm = ChatOpenAI(model=..., temperature=0.1)
response = llm.invoke(messages)
content = response.content.strip()
if content.startswith("```"):
    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
data = json.loads(content)

# 改造后
structured_llm = get_structured_llm(IntakeOutput, temperature=0.1)
output: IntakeOutput = structured_llm.invoke(messages)
patient_dict = output.model_dump(mode="json")
```

**改动文件**：新增 `models/llm_outputs.py`，重写 4 个 Agent

---

### P0-1：Service 层与 Agent 集成

| Agent | 改造前 | 改造后 |
|-------|--------|--------|
| **Diagnosis** | LLM 凭空推理疾病 | 先调 `graphrag_service.find_diseases_by_symptoms()` 做确定性检索，结果注入 LLM context 作为参考 |
| **Treatment** | LLM 凭空判断 DDI 和过敏 | LLM 生成候选药物 → 调 `drug_interaction.check_interactions()` + `check_allergy_contraindication()` 做确定性检查 → 合并结果，过滤禁忌药物 |
| **Coding** | LLM 凭空生成 ICD-10 编码 | LLM 生成编码 → 调 `icd10_service.lookup_icd10()` 校验 → 不存在则 `search_icd10_by_text()` 回退 → `get_drg_group()` 获取真实 DRG |

**改动文件**：`diagnosis_agent.py`、`treatment_agent.py`、`coding_agent.py`

---

## 三、P1 — 可用性提升

### P1-1：LLM 单例 + Prompt Caching

| 改造前 | 改造后 |
|--------|--------|
| 5 个 Agent 各自 `ChatOpenAI(...)` 创建实例 | `config/llm.py` 提供 `get_llm(temperature)` 按温度缓存单例 |
| 每次调用重新建 HTTP 连接 | 共享 `httpx.Client` 连接池（5 keepalive / 20 max） |
| 每次重新发送相同 system prompt | OpenAI 自动缓存 >1024 token 前缀，仅首次传输完整 prompt |
| 不支持自定义 API 地址 | 新增 `openai_base_url` 配置，支持 DeepSeek 等兼容 API |

**改动文件**：新增 `config/llm.py`，修改 4 个 Agent 和 `settings.py`

---

### P1-2：SSE 流式输出

| 改造前 | 改造后 |
|--------|--------|
| `pipeline.invoke()` 同步阻塞 15-30 秒后一次性返回 | 新增 `POST /clinical/analyze/stream`，使用 `astream_events` 逐个 Agent 推送 SSE 事件 |
| 前端显示空白 loading | 前端可逐阶段渲染：Intake → Diagnosis → Treatment → Coding → Audit |
| 单一端点 | 保留原 `/clinical/analyze` 同步端点 + 新增 `/clinical/analyze/stream` 流式端点 |

**改动文件**：`routes.py`（+流式端点函数）

---

### P1-3：Agent/Pipeline 测试

| 改造前 | 改造后 |
|--------|--------|
| 0 个 Agent/Pipeline 测试 | 30 个测试（15 Agent + 15 Service） |
| 仅 `test_services.py`（15 个 Service 层测试） | 新增 `test_agents.py`（15 个：错误处理 8 + 路由逻辑 4 + State 模型 3） |
| 无管线路由测试 | Pipeline 路由全覆盖：正常路径 / 回退循环 / 循环上限 / 初始状态 |

**测试覆盖**：Intake 空输入、Diagnosis 无患者信息、Treatment 无诊断、Coding 无诊断、Audit PHI 检测、Pipeline 所有路由分支、State 默认值

**改动文件**：新增 `tests/test_agents.py`

---

## 四、P2 — 生产化深化

### P2-2：知识库扩展

| 模块 | 改造前 | 改造后 |
|------|--------|--------|
| **ICD-10 编码** | 30 条硬编码 dict | CMS 2026 XML → SQLite，36,343 条可计费编码，LIKE 模糊搜索含相关性排序 |
| **DDI 数据库** | 10 条英文条目 | 85+ 条，全部中文药物名，覆盖抗生素/心血管/降糖/精神科/抗凝/NSAID 6 大类 |
| **药物类别映射** | 14 个英文映射 | 108 个中英文药物名→类别标识符映射 |
| **GraphRAG 症状** | 11 种英文症状 | 50+ 种中文症状，每症状对应 5-15 个候选疾病，支持模糊匹配 |
| **GraphRAG 疾病** | 15 条英文疾病→编码 | 200+ 条中英文疾病→ICD-10 编码，覆盖 22 个 ICD-10 章节 |
| **过敏检查** | 简单字符串匹配 | 青霉素交叉反应（头孢类~10%）、磺胺过敏识别 |

**改动文件**：`icd10_service.py`（SQLite）、`drug_interaction.py`（200+条）、`graphrag_service.py`（50+/200+）、新增 `scripts/import_icd10.py`

---

### P2-4：HIPAA → 中国数据合规审计

| 改造前 | 改造后 |
|--------|--------|
| 8 项 HIPAA 合规检查 **全部硬编码 True** | 10 项中国法律合规检查：PIPL 第 6/19/28/38/44-47/50/51/55/57 条 + 数据安全法第 27 条 + 健康医疗大数据管理办法 |
| PHI 正则粗糙（IP 地址会误匹配血常规数值 `15,000`） | 精确正则：身份证号含校验位、手机号/医保卡号/中文地址/基因数据等中国特色标识符 |
| 无环境状态检查 | 9 项检查通过 `os.getenv()` 读取实际系统配置状态（`APP_HTTPS_ENABLED`、`DB_ENCRYPTION_ENABLED` 等） |
| PHI 报告只列字段名 | 检出报告包含字段名 + 出现次数 + 前 5 条匹配样本 |
| 18 项 HIPAA 标识符 | 18 项中国敏感个人信息：身份证号/手机号/医保卡号/中文姓名/指纹/基因数据/健康档案等 |

```python
# 改造前：硬编码
structural_checks = {
    "data_encryption_at_rest": True,   # 从不验证
    "access_control_rbac": True,       # 从不验证
    ...
}

# 改造后：接入系统状态
COMPLIANCE_CHECKS_CONFIG = [
    {"check_name": "数据传输加密", "requirement": "PIPL 第51条",
     "check_func": lambda: _check_env_true("APP_HTTPS_ENABLED")},
    {"check_name": "跨境数据传输审批", "requirement": "PIPL 第38条",
     "check_func": lambda: _check_env_true("CROSS_BORDER_APPROVED")},
    ...
]
```

**改动文件**：`audit_agent.py`（完全重写）

---

### P2-1：持久化 Checkpointer

| 改造前 | 改造后 |
|--------|--------|
| `MemorySaver()` 内存存储 | `SqliteSaver` 磁盘持久化 → `data/checkpoints.db` |
| 进程重启丢失所有会话状态 | 会话跨进程保留，支持会话恢复 |
| 无 fallback | SqliteSaver 不可用时自动回退 MemorySaver |

**改动文件**：`clinical_pipeline.py`（`_create_checkpointer()` + 自动回退逻辑）

---

### P2-3：输入安全防护

| 改造前 | 改造后 |
|--------|--------|
| 仅 `min_length=10` 校验 | 三层防护：Prompt injection 检测（14 条正则/中英文）+ 输入长度上限 5000 字符 + Pydantic schema 校验 |
| 用户可提交 `ignore previous instructions...` 类攻击 | 检测到 injection 模式 → 返回 HTTP 400 |
| 无 token 消耗攻击防护 | 5000 字符上限防止恶意超长输入 |

```python
# 改造后：每个端点调用前执行
def _validate_input(patient_description: str) -> None:
    if len(patient_description) > MAX_INPUT_LENGTH:
        raise HTTPException(400, f"输入过长...")
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, patient_description, re.IGNORECASE):
            raise HTTPException(400, "输入包含无效内容")
```

**改动文件**：`routes.py`（+`_validate_input()` + 同步/流式两个端点调用）

---

## 五、测试覆盖总览

```
30 passed, 0 failed

service tests (15):  ICD-10 5 + DDI 4 + HIPAA 4 + GraphRAG 2
agent tests  (15):  Intake 2 + Diagnosis 2 + Treatment 1 + Coding 1
                     + Audit 2 + Pipeline routing 4 + State 3
```

---

## 六、全部改动文件清单

| 文件 | 改动类型 | 所属优化项 |
|------|----------|-----------|
| `models/llm_outputs.py` | 新增 | P0-2 |
| `agents/intake_agent.py` | 重写 | P0-1/2/3, P1-1 |
| `agents/diagnosis_agent.py` | 重写 | P0-1/2, P1-1 |
| `agents/treatment_agent.py` | 重写 | P0-1/2, P1-1 |
| `agents/coding_agent.py` | 重写 | P0-1/2, P1-1 |
| `agents/audit_agent.py` | 重写 | P2-4 |
| `graph/state.py` | 修改 | P0-3 |
| `graph/clinical_pipeline.py` | 重写 | P0-3, P2-1 |
| `config/llm.py` | 新增 | P1-1 |
| `config/settings.py` | 修改 | P1-1 |
| `api/routes.py` | 修改 | P1-2, P2-3 |
| `services/icd10_service.py` | 重写 | P2-2 |
| `services/drug_interaction.py` | 重写 | P2-2 |
| `services/graphrag_service.py` | 重写 | P2-2 |
| `scripts/import_icd10.py` | 新增 | P2-2 |
| `tests/test_agents.py` | 新增 | P1-3 |
| `tests/test_services.py` | 修改 | P2-2 |
