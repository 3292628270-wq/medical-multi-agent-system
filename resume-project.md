# 简历项目经历

> 以下为不同长度的版本，根据简历排版空间选择。内容基于项目当前实际状态编写。

---

## 标准版（推荐实习简历使用，6-8行）

### 多Agent医疗临床辅助决策系统

**2026.02 — 2026.04** | 个人项目 | Python / LangGraph / FastAPI / React / TypeScript

- 基于 **LangGraph StateGraph** 构建 5-Agent 协作管线（接诊→诊断→治疗→ICD-10编码→合规审计），以共享状态 + 条件路由实现临床决策全流程自动化，单次分析约 2 分钟
- 自建**医学知识图谱**（50+症状→200+疾病→ICD-10编码映射）+ ICD-10 编码库（CMS 2026 官方数据，36,343 条）+ 药物相互作用数据库（200+条），注入 LLM 推理链路解决幻觉问题
- 采用**确定性校验 + LLM 推理双层设计**：治疗 Agent 先经 LLM 生成用药候选，再调用 DDI 数据库做药物相互作用检查 + 过敏交叉验证，过滤禁忌药物后输出最终方案
- 实现 **SSE 流式传输**，配合 React 前端 Pipeline 可视化组件逐阶段渲染 5 个 Agent 执行状态；侧边栏集成 ICD-10 编码搜索和药物相互作用检查
- 审计模块覆盖 10 项中国数据合规检查（PIPL/数据安全法/健康医疗大数据管理办法），支持敏感信息扫描脱敏和不可变审计日志生成
- 编写 **30 个 pytest 单元测试**（Agent 错误处理 + Pipeline 路由逻辑 + Service 层），全链路通过；LLM 调用层封装兼容 OpenAI / DeepSeek 双后端

**技术栈**：Python 3.11 · LangGraph 0.2+ · FastAPI · React 18 · TypeScript · LangChain · Pydantic · SQLite · SSE · Docker

---

## 详细版（10-12行，适合技能突出的简历）

### 多Agent医疗临床辅助决策系统

**2026.02 — 2026.04** | 后端 & 前端全栈 | Python / LangGraph / FastAPI / React 18 / TypeScript

**项目概述**：构建了一个企业级医疗 AI 辅助决策系统，模拟真实医院诊疗流程中的 5 个专业角色（接诊护士→诊断医师→临床药师→病案编码员→合规审计员），通过 LangGraph StateGraph 编排为协作管线，实现对自由文本患者描述的端到端结构化分析。配套 React 前端提供 Pipeline 可视化、SSE 流式结果展示、ICD-10 编码搜索和药物相互作用检查。

**架构设计**：
- 采用 Pipeline 编排模式 + 条件路由：Diagnosis Agent 判断信息不足时自动回退 Intake Agent 重新收集（上限 3 次），模拟真实分诊场景
- 定义 ClinicalState 共享状态模型（Pydantic），5 个 Agent 各自读写负责字段，状态变更可追踪
- 前端通过 SSE 消费 `astream_events` 事件流，Pipeline 状态图和 Agent 结果卡片逐步呈现

**LLM 幻觉防御（三层设计）**：
- 第一层 — 知识图谱检索：诊断 Agent 基于医学知识图谱做症状→疾病确定性匹配，结果注入 LLM context 作为参考
- 第二层 — 确定性校验：治疗 Agent 经 LLM 生成用药候选后，调用 DDI 数据库（200+条）+ 过敏交叉验证去过滤
- 第三层 — 编码验证：Coding Agent 生成的 ICD-10 编码经 SQLite（36,343 条 CMS 官方数据）校验，不存在时自动 LIKE 模糊回退

**合规与安全**：
- 审计 Agent 不使用 LLM（纯规则引擎），覆盖 10 项中国数据合规检查（PIPL 第 6/19/28/38/44-47/50/51/55/57 条、数据安全法第 27 条、健康医疗大数据管理办法），其中 3 项接入系统状态实时验证
- 敏感信息扫描 + 脱敏（身份证号/手机号/邮箱等）+ 不可变审计日志 + 输出字段最小化校验
- 输入层 Prompt Injection 防护 + 5,000 字符上限

**前端（React + TypeScript + Vite）**：
- 患者信息表单（内置示例病例一键填充）
- 5 节点 Pipeline 状态图（实时显示等待/执行中/完成）
- 5 张 Agent 结果卡片（针对接诊/诊断/治疗/编码/审计各自定制渲染）
- 侧边栏：ICD-10 编码搜索 + 药物相互作用检查
- SSE 流式接收 + 响应式设计

**工程化**：
- LLM 调用层封装双层策略（优先 OpenAI native structured output → 失败降级 Prompt 注入 + json.loads），兼容 DeepSeek API
- LLM 实例按温度缓存单例 + httpx 连接池复用
- 30 个 pytest 测试（Agent 错误处理 + Pipeline 路由 + Service 层），全通过
- 8 个线上 Bug 记录在 bug-fixes.md（现象→原因→方案）

**技术栈**：Python 3.11 · LangGraph 0.2+ · LangChain · FastAPI · React 18 · TypeScript · Vite · Pydantic · SQLite · SSE · structlog · pytest · Docker

---

## 精炼版（4行，适合空间极度有限的简历）

**多Agent医疗临床辅助决策系统** | Python / LangGraph / FastAPI / React | 2026.02 — 2026.04

- 基于 LangGraph 编排 5 个 LLM Agent 协作完成接诊→诊断→治疗→ICD-10编码→合规审计全流程，集成医学知识图谱检索辅助诊断
- 自建医学知识图谱（ICD-10 36k+条、DDI 200+条、症状-疾病映射50+），设计"知识图谱检索→确定性校验→编码验证"三层幻觉防御机制
- 实现 SSE 流式输出 + React Pipeline 可视化前端 + 侧边栏 ICD-10/DDI 查询工具；LLM 层兼容 OpenAI/DeepSeek 双后端
- 30 个 pytest 测试全覆盖；审计模块实现 PIPL/数据安全法 10 项合规检查，3 项接入系统状态实时验证

---

## 面试 STAR 法回答

**Situation — 背景**

医疗 AI 辅助决策是一个典型的多步骤推理场景——从患者自由文本描述到最终 ICD-10 编码，需要经过信息提取、鉴别诊断、用药方案、编码分配、合规审计五个专业环节。单一 LLM 调用难以覆盖全部推理深度，且存在幻觉风险。

**Task — 任务**

构建一个多 Agent 协作系统：5 个 Agent 各自专注一个专业领域，通过管线编排完成端到端临床决策，同时解决三个核心难题——LLM 幻觉、模型 API 兼容性、医疗数据合规。

**Action — 行动**

- **编排层**：LangGraph StateGraph + ClinicalState 共享状态 + 条件路由（信息不足时自动回退补采）
- **幻觉防御**：知识图谱检索（症状→疾病→编码，先查再推）→ 确定性校验（DDI 数据库检查后再输出）→ 编码验证（SQLite 校验 + 模糊回退）
- **合规设计**：审计 Agent 不使用 LLM（纯规则引擎），覆盖 10 项 PIPL/数据安全法检查，敏感信息扫描脱敏 + 不可变审计日志
- **前端可视化**：React SSE 流式渲染 Pipeline 状态图，5 张 Agent 结果卡片逐步呈现
- **质量保障**：30 个 pytest 测试 + LLM 双层降级策略（structured output / Prompt 注入兼容 OpenAI/DeepSeek）

**Result — 成果**

- ICD-10 编码覆盖 36,343 条（CMS 2026 官方数据），DDI 数据库 200+ 条，医学知识图谱覆盖 50+ 症状→200+ 疾病
- 诊断/治疗/编码三个阶段从纯 LLM 生成 → 检索增强 + 确定性校验
- 审计模块从硬编码检查 → 10 项中国法律框架下的合规检查（3 项实时验证）
- 全链路在 DeepSeek API 环境下跑通，0 errors；30 个测试全部通过

---

## 面试追问准备

| 追问方向 | 回答要点 |
|---------|---------|
| 为什么用 LangGraph 而不是自己写编排？ | StateGraph 声明式 API + 内置 checkpoint + 条件路由 + astream_events 原生流式支持 |
| 怎么解决 LLM 幻觉？ | 三层防御：知识图谱检索 → Service 确定性校验 → model_validator 兜底 |
| DeepSeek 兼容怎么做的？ | try structured_output → catch "response_format" error → fallback Prompt + json.loads + schema 注入 |
| 5 个 Agent 串行怎么优化？ | 当前约 2 分钟；后续可用 Send API 并行 Diagnosis+Treatment、LLM 单例复用、Prompt Caching |
| Pipeline 可视化怎么实现？ | astream_events(v2) → on_chain_end 过滤 → SSE 推送 → React useState 更新 → CSS transition |
| ICD-10 36k 编码怎么导入的？ | CMS 2026 XML → 递归解析 leaf diag → SQLite → lookup_icd10 精确查找 → LIKE 模糊回退 |
| 为什么审计 Agent 不用 LLM？ | 合规检查需 100% 确定性、PHI 不应发给第三方 LLM、规则引擎 <0.1s 比 LLM 快 30 倍 |
| 知识图谱怎么实现的？ | 当前使用症状→疾病→ICD-10 三层映射结构做确定性检索（50+ 症状→200+ 疾病），下一步计划用 Neo4j 图数据库升级存储引擎，支持 Cypher 多跳查询 |

---

## 下一步优化方向（面试时可以提）

| 方向 | 说明 |
|------|------|
| **知识图谱升级（Neo4j）** | 当前知识图谱为内存结构（Python dict），计划用 Neo4j 图数据库升级存储引擎，支持 Cypher 多跳查询（症状→疾病→治疗路径） |
| **流式 LLM 输出** | 当前 Agent 内部仍是同步调用，计划将每个 Agent 的 LLM 调用也改为 token 级流式 |
| **PostgreSQL 持久化** | 当前使用 MemorySaver，计划接入 PostgresSaver 实现跨进程会话恢复 |
| **更多科室覆盖** | 扩展 Agent 支持更多专科（骨科、儿科、妇产科等） |
