# Multi-Agent Clinical Decision Support System (Go)

基于 Go + Gin + OpenAI 的多 Agent 医疗临床辅助决策系统。

## 架构

五个专业化 Agent 按顺序协作，通过 Pipeline 编排：

```
Intake → Diagnosis ──(needs_more_info?)──→ Intake (最多重试2次)
                   └──(ready)──→ Treatment → Coding → Audit → END
```

| Agent | 职责 | 引擎 |
|-------|------|------|
| **Intake** | 解析患者描述为结构化数据 | LLM (OpenAI) |
| **Diagnosis** | 生成鉴别诊断列表 | LLM (OpenAI) |
| **Treatment** | 制定循证治疗方案 + 药物交互检查 | LLM (OpenAI) |
| **Coding** | ICD-10 编码 + DRGs 分组 | LLM (OpenAI) |
| **Audit** | HIPAA 合规检查、PHI 扫描、数据脱敏 | 纯规则引擎 |

## 快速开始

### 前置条件

- Go 1.22+
- OpenAI API Key

### 本地运行

```bash
export OPENAI_API_KEY="your-key-here"
go mod tidy
go run ./cmd/server
```

服务默认监听 `:8090`。

### Docker 运行

```bash
export OPENAI_API_KEY="your-key-here"
docker compose up --build
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/clinical/analyze` | 运行完整 5-Agent 临床决策管线 |
| POST | `/api/v1/clinical/icd10/search` | 按文本搜索 ICD-10 编码 |
| GET | `/api/v1/clinical/icd10/:code` | 查询单个 ICD-10 编码 |
| POST | `/api/v1/clinical/ddi/check` | 药物-药物交互检查 |
| GET | `/health` | 健康检查 |

### 示例请求

```bash
curl -X POST http://localhost:8090/api/v1/clinical/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "patient_description": "45-year-old male presenting with fever (39.2°C) for 3 days, productive cough with yellow sputum, and right-sided chest pain. History of type 2 diabetes and hypertension. Current medications: metformin 500mg BID, lisinopril 10mg daily. Allergies: penicillin (rash). Labs: WBC 15,000/μL, CRP 85 mg/L, chest X-ray shows right lower lobe infiltrate."
  }'
```

## 项目结构

```
go/
├── cmd/server/main.go           # 入口
├── internal/
│   ├── agent/
│   │   ├── base.go              # Agent 接口 + LLM 调用辅助
│   │   ├── intake.go            # Intake Agent
│   │   ├── diagnosis.go         # Diagnosis Agent
│   │   ├── treatment.go         # Treatment Agent
│   │   ├── coding.go            # Coding Agent
│   │   └── audit.go             # Audit Agent (纯规则)
│   ├── config/config.go         # 环境变量配置
│   ├── graph/pipeline.go        # Pipeline 编排
│   ├── handler/clinical.go      # Gin HTTP 处理器
│   ├── model/state.go           # 数据模型
│   └── service/
│       ├── icd10.go             # ICD-10 编码库
│       ├── drug_interaction.go  # 药物交互数据库
│       ├── fhir.go              # FHIR R4 转换
│       └── hipaa.go             # HIPAA 合规服务
├── Dockerfile
├── docker-compose.yml
└── go.mod
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | (必填) | OpenAI API 密钥 |
| `OPENAI_MODEL` | `gpt-4o-mini` | 使用的模型 |
| `SERVER_PORT` | `8090` | 服务端口 |
| `POSTGRES_DSN` | `postgres://...` | PostgreSQL 连接串 |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j 连接 |
| `REDIS_ADDR` | `localhost:6379` | Redis 地址 |
