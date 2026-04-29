# 多Agent医疗临床辅助决策系统

基于 **LangGraph** 编排 5 个 LLM Agent 协作完成接诊→诊断→治疗→ICD-10编码→合规审计全流程。

---

## 系统架构

```
POST /api/v1/clinical/analyze        POST /api/v1/clinical/analyze/stream (SSE)
        │                                      │
        ▼                                      ▼
  ┌─ 输入安全防护 ────────────────────────────── SSE 逐个返回Agent结果
  │ Prompt injection检测 + 5000字符上限
  └──────────────────────────────────────┘
        │
        ▼
  Intake ──(structured output)──▶ patient_info
        │
        ▼
  Diagnosis ──(KG Jaccard召回→LLM推理→证据评分)──▶ diagnosis
        │                                    │
        │   needs_more_info=true             │
        │   ◀──── 回退重采(上限3次)           │
        │                                    │
        ▼                                    │
  Treatment ──(LLM→DDI检查→KG药物推荐)──▶ treatment_plan
        │
        ▼
  Coding ──(LLM→ICD-10 SQLite校验)──▶ coding_result
        │
        ▼
  Audit ──(PIPL/数据安全法审查)──▶ audit_result
        │
        ▼
  MemorySaver checkpoints + 30个测试覆盖
```

### 五个 Agent

| Agent | 类比 | 核心能力 |
|-------|------|---------|
| **Intake 接诊** | 分诊护士 | 将自由文本患者描述解析为结构化 PatientInfo（11个字段） |
| **Diagnosis 诊断** | 主治医师 | KG Jaccard 检索 → LLM 鉴别诊断 → 证据评分覆盖置信度 |
| **Treatment 治疗** | 临床药师 | LLM 生成用药候选 → DDI 数据库(200+条)确定性检查 → KG 药物推荐 |
| **Coding 编码** | 病案编码员 | LLM 生成 ICD-10 → SQLite(36,343条)校验 → 不存在时 LIKE 回退 → DRG 分组 |
| **Audit 审计** | 合规官 | 纯规则引擎(不使用LLM)，覆盖 PIPL/数据安全法 10 项合规检查 |

### 诊断流程（三步）

```
Step 1: KG 召回 (Jaccard 相似度)
  CMeIE 知识图谱: 3,621疾病 × 6,384症状 × 2,056药物
  患者症状 → symptom_disease 倒排索引 → Jaccard排序 → top 30

Step 2: LLM 推理
  Prompt = 患者数据 + top-3 KG候选(症状/药物/检查/鉴别诊断/并发症)
  → 主要诊断 + 鉴别诊断列表

Step 3: 证据评分 (确定性置信度)
  疾病核心症状12个, 患者命中N个 → 匹配率 N/12
  置信度 = max(LLM主观置信度, 证据匹配率)
```

---

## 快速开始

### 环境要求

- Python 3.11+
- DeepSeek API Key（或 OpenAI 兼容 API）
- Node.js（前端开发用）

### 启动后端

```bash
cd python
pip install -r requirements.txt
cp .env.example .env   # 编辑 .env 填入 API Key

# .env 配置示例 (DeepSeek):
#   OPENAI_API_KEY=sk-xxxx
#   OPENAI_MODEL=deepseek-v4-flash
#   OPENAI_BASE_URL=https://api.deepseek.com

uvicorn src.api.main:app --port 8000 --reload
```

访问 http://localhost:8000/docs 查看 API 文档。

### 启动前端

```bash
cd frontend
npm install
npm run dev        # → http://localhost:5173
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/clinical/analyze` | 完整 5-Agent 管线（同步） |
| `POST` | `/api/v1/clinical/analyze/stream` | 完整 5-Agent 管线（SSE 流式） |
| `POST` | `/api/v1/clinical/icd10/search` | ICD-10 编码搜索 |
| `GET` | `/api/v1/clinical/icd10/{code}` | ICD-10 编码查询 + DRG |
| `POST` | `/api/v1/clinical/ddi/check` | 药物相互作用检查 |
| `GET` | `/health` | 健康检查 |

### 测试

```bash
cd python
pytest tests/ -v    # 30 个测试
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| **Agent 编排** | LangGraph 0.2+ (StateGraph + 条件路由 + checkpoint) |
| **LLM** | DeepSeek V4 Flash（兼容 OpenAI API，自动 fallback 无 structured output） |
| **后端** | FastAPI + Pydantic v2 + LangChain |
| **知识图谱** | CMeIE 数据集 (36,892 三元组) → SQLite + Jaccard 检索 |
| **编码库** | CMS 2026 ICD-10-CM → SQLite (36,343 条) |
| **DDI 库** | 自建 200+ 条中文药物相互作用数据库 |
| **前端** | React 18 + TypeScript + Vite + SSE |
| **LLM 调用** | 按温度缓存单例 + httpx 连接池 + structured output/Prompt 双模 |

---

## 项目结构

```
python/
├── src/
│   ├── agents/
│   │   ├── intake_agent.py        # 接诊 Agent
│   │   ├── diagnosis_agent.py     # 诊断 Agent (KG+LLM+证据)
│   │   ├── treatment_agent.py     # 治疗 Agent (DDI+KG药物)
│   │   ├── coding_agent.py        # 编码 Agent (ICD-10校验)
│   │   └── audit_agent.py         # 审计 Agent (10项合规检查)
│   ├── api/
│   │   ├── main.py                # FastAPI 入口
│   │   └── routes.py              # API 端点 + 输入安全
│   ├── graph/
│   │   ├── clinical_pipeline.py   # LangGraph 管线编排
│   │   └── state.py               # ClinicalState 共享状态
│   ├── models/
│   │   ├── llm_outputs.py         # LLM 结构化输出模型
│   │   ├── patient.py             # PatientInfo Pydantic
│   │   ├── diagnosis.py           # DifferentialDiagnosis
│   │   └── treatment.py           # TreatmentPlan/CodingResult/AuditResult
│   ├── services/
│   │   ├── graphrag_service.py    # CMeIE 知识图谱 (Jaccard+证据)
│   │   ├── icd10_service.py       # ICD-10 SQLite 查询
│   │   ├── drug_interaction.py    # DDI 数据库 (200+条)
│   │   ├── fhir_service.py        # FHIR R4 序列化
│   │   └── hipaa_service.py       # PHI 检测/脱敏
│   └── config/
│       ├── settings.py            # 环境变量配置
│       └── llm.py                 # LLM 单例 + fallback
├── scripts/
│   ├── import_icd10.py             # CMS XML → SQLite
│   └── import_cmeie_kg.py          # CMeIE JSONL → SQLite KG
├── tests/
│   ├── test_services.py            # Service 层测试 (15个)
│   └── test_agents.py              # Agent + Pipeline 测试 (15个)
├── data/
│   ├── icd10.db                    # ICD-10 编码库
│   ├── cmeie_kg.db                 # CMeIE 知识图谱
│   └── CMeIE/                      # CMeIE 原始数据
└── static/                         # 静态文件（FastAPI serving）

frontend/
└── src/
    ├── App.tsx                     # 主布局
    ├── hooks/useSSE.ts             # SSE 流式 Hook
    └── components/
        ├── PatientForm.tsx          # 患者表单
        ├── PipelineView.tsx         # Pipeline 可视化
        ├── AgentCard.tsx            # Agent 结果卡片（5种渲染）
        └── Sidebar.tsx              # ICD-10/DDI 侧边栏
```

---

## Bug 修复记录 & 优化方案

- [bug-fixes.md](bug-fixes.md) — 8 个线上 Bug 的现象/原因/修复方案
- [optimization-plan.md](optimization-plan.md) — 11 项 P0/P1/P2 优化的改造前/后对比
- [resume-project.md](resume-project.md) — 简历项目经历（三种长度 + STAR 模板）
