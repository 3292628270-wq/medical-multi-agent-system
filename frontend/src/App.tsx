import React from 'react'
import { useClinicalPipeline } from './hooks/useSSE'
import { PatientForm } from './components/PatientForm'
import { PipelineView } from './components/PipelineView'
import { AgentCard } from './components/AgentCard'
import { Sidebar } from './components/Sidebar'
import './App.css'

const App: React.FC = () => {
  const { loading, agents, error, runPipeline, cancel } = useClinicalPipeline()

  const handleSubmit = (text: string) => {
    runPipeline(text)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>🏥 多Agent医疗临床辅助决策系统</h1>
        <span className="version">v2.0</span>
      </header>

      <div className="app-body">
        <main className="main-content">
          <PatientForm onSubmit={handleSubmit} loading={loading} onCancel={cancel} />

          {error && (
            <div className="error-banner">
              <span>❌ {error}</span>
            </div>
          )}

          <PipelineView agents={agents} loading={loading} />

          <div className="results-area">
            {agents.map(agent => (
              <AgentCard key={agent.name} agent={agent} />
            ))}
          </div>

          {agents.every(a => a.status === 'pending') && !loading && !error && (
            <div className="empty-state">
              <div className="empty-icon">📝</div>
              <h3>开始临床决策分析</h3>
              <p>输入患者描述，系统将通过 5 个专业 Agent 协作完成：</p>
              <ol>
                <li><strong>接诊 Agent</strong> — 结构化提取患者信息</li>
                <li><strong>诊断 Agent</strong> — 鉴别诊断 + 知识图谱检索</li>
                <li><strong>治疗 Agent</strong> — 循证方案 + 药物相互作用检查</li>
                <li><strong>编码 Agent</strong> — ICD-10 编码 + DRG 分组</li>
                <li><strong>审计 Agent</strong> — 数据合规审计（PIPL）</li>
              </ol>
            </div>
          )}
        </main>

        <Sidebar />
      </div>
    </div>
  )
}

export default App
