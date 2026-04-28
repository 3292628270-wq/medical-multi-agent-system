import React from 'react'
import type { AgentStatus, PatientInfo, DiagnosisData, TreatmentData, CodingData, AuditData } from '../types'

interface Props {
  agent: AgentStatus
}

function renderPatientInfo(data: PatientInfo) {
  return (
    <div className="agent-data">
      <div className="info-grid">
        <div className="info-item"><label>姓名</label><span>{data.name}</span></div>
        <div className="info-item"><label>年龄</label><span>{data.age}岁</span></div>
        <div className="info-item"><label>性别</label><span>{data.gender}</span></div>
        <div className="info-item"><label>主诉</label><span>{data.chief_complaint}</span></div>
      </div>
      {data.symptoms?.length > 0 && (
        <div className="info-section">
          <label>症状</label>
          <ul>{data.symptoms.map((s, i) => (
            <li key={i}>{s.name} · {s.severity}{s.duration_days ? ` · ${s.duration_days}天` : ''}</li>
          ))}</ul>
        </div>
      )}
      {data.medical_history?.length > 0 && (
        <div className="info-section">
          <label>既往病史</label>
          <ul>{data.medical_history.map((h, i) => <li key={i}>{h}</li>)}</ul>
        </div>
      )}
      {data.allergies?.length > 0 && (
        <div className="info-section">
          <label>过敏史</label>
          <ul>{data.allergies.map((a, i) => (
            <li key={i}>{a.substance}{a.reaction ? ` → ${a.reaction}` : ''} · {a.severity}</li>
          ))}</ul>
        </div>
      )}
      {data.current_medications?.length > 0 && (
        <div className="info-section">
          <label>当前用药</label>
          <ul>{data.current_medications.map((m, i) => (
            <li key={i}>{m.name}{m.dosage ? ` ${m.dosage}` : ''}{m.frequency ? ` ${m.frequency}` : ''}</li>
          ))}</ul>
        </div>
      )}
    </div>
  )
}

function renderDiagnosis(data: DiagnosisData) {
  return (
    <div className="agent-data">
      <div className="primary-dx">
        <div className="dx-header">
          <span className="dx-name">{data.primary_diagnosis.disease_name}</span>
          <span className="dx-code">{data.primary_diagnosis.icd10_hint}</span>
          <span className="dx-confidence">置信度 {(data.primary_diagnosis.confidence * 100).toFixed(0)}%</span>
        </div>
        <p className="dx-reasoning">{data.primary_diagnosis.reasoning}</p>
        {data.primary_diagnosis.evidence?.length > 0 && (
          <div className="dx-evidence">
            <label>证据：</label>
            <ul>{data.primary_diagnosis.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
          </div>
        )}
      </div>
      {data.differential_list?.length > 0 && (
        <div className="diff-list">
          <label>鉴别诊断：</label>
          {data.differential_list.map((d, i) => (
            <div key={i} className="diff-item">
              <span className="dx-name">{d.disease_name}</span>
              <span className="dx-code">{d.icd10_hint}</span>
              <span className="dx-confidence">{(d.confidence * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
      {data.recommended_tests?.length > 0 && (
        <div className="info-section">
          <label>建议检查</label>
          <ul>{data.recommended_tests.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
      )}
    </div>
  )
}

function renderTreatment(data: TreatmentData) {
  return (
    <div className="agent-data">
      <p className="dx-addressed">目标诊断：{data.diagnosis_addressed}</p>
      {data.medications?.length > 0 && (
        <div className="info-section">
          <label>用药方案</label>
          {data.medications.map((m, i) => (
            <div key={i} className="med-card">
              <div className="med-header">
                <strong>{m.drug_name}</strong>
                {m.generic_name && <span className="generic">({m.generic_name})</span>}
              </div>
              <div className="med-detail">
                {m.dosage} · {m.route} · {m.frequency} · {m.duration}
              </div>
              {m.side_effects?.length > 0 && (
                <div className="med-side-effects">副作用：{m.side_effects.join('、')}</div>
              )}
            </div>
          ))}
        </div>
      )}
      {data.drug_interactions?.length > 0 && (
        <div className="info-section">
          <label>药物相互作用</label>
          {data.drug_interactions.map((ddi, i) => (
            <div key={i} className={`ddi-card severity-${ddi.severity}`}>
              <div className="ddi-pair">{ddi.drug_a} + {ddi.drug_b}</div>
              <span className={`ddi-severity ${ddi.severity}`}>{ddi.severity}</span>
              <p>{ddi.description}</p>
              <p className="ddi-rec">建议：{ddi.recommendation}</p>
            </div>
          ))}
        </div>
      )}
      {data.warnings?.length > 0 && (
        <div className="info-section warnings">
          <label>⚠️ 警告</label>
          {data.warnings.map((w, i) => <p key={i} className="warning-item">{w}</p>)}
        </div>
      )}
      {data.non_drug_treatments?.length > 0 && (
        <div className="info-section">
          <label>非药物治疗</label>
          <ul>{data.non_drug_treatments.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
      )}
      {data.follow_up_plan && (
        <div className="info-section">
          <label>随访计划</label>
          <p>{data.follow_up_plan}</p>
        </div>
      )}
    </div>
  )
}

function renderCoding(data: CodingData) {
  return (
    <div className="agent-data">
      <div className="info-section">
        <label>主要 ICD-10 编码</label>
        <div className="code-primary">
          <span className="code">{data.primary_icd10.code}</span>
          <span className="desc">{data.primary_icd10.description}</span>
          <span className="conf">置信度 {(data.primary_icd10.confidence * 100).toFixed(0)}%</span>
        </div>
      </div>
      {data.secondary_icd10_codes?.length > 0 && (
        <div className="info-section">
          <label>次要编码</label>
          {data.secondary_icd10_codes.map((c, i) => (
            <div key={i} className="code-secondary">
              <span className="code">{c.code}</span>
              <span className="desc">{c.description}</span>
              <span className="conf">{(c.confidence * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
      {data.drg_group && (
        <div className="info-section">
          <label>DRG 分组</label>
          <div className="drg-card">
            <div className="drg-code">DRG {data.drg_group.drg_code}</div>
            <div className="drg-desc">{data.drg_group.description}</div>
            <div className="drg-stats">
              权重 {data.drg_group.weight} · 平均住院 {data.drg_group.mean_los} 天
            </div>
          </div>
        </div>
      )}
      {data.coding_notes && (
        <div className="info-section">
          <label>编码说明</label>
          <p>{data.coding_notes}</p>
        </div>
      )}
    </div>
  )
}

function renderAudit(data: AuditData) {
  return (
    <div className="agent-data">
      <div className={`audit-badge ${data.overall_risk_level === '低' ? 'pass' : data.overall_risk_level === '中' ? 'warn' : 'fail'}`}>
        {data.overall_risk_level === '低' ? '✅ 合规' : data.overall_risk_level === '中' ? '⚠️ 需关注' : '❌ 高风险'}
        <span className="risk-level">风险等级：{data.overall_risk_level}</span>
      </div>
      {data.compliance_checks?.length > 0 && (
        <div className="info-section">
          <label>合规检查项</label>
          {data.compliance_checks.map((c, i) => (
            <div key={i} className={`check-item ${c.passed ? 'pass' : 'fail'}`}>
              <span className="check-icon">{c.passed ? '✅' : '❌'}</span>
              <div>
                <strong>{c.check_name}</strong>
                <p>{c.detail}</p>
              </div>
            </div>
          ))}
        </div>
      )}
      {data.phi_fields_found?.length > 0 && (
        <div className="info-section warnings">
          <label>检出敏感信息</label>
          <p>{data.phi_fields_found.join('、')}</p>
        </div>
      )}
      {data.recommendations?.length > 0 && (
        <div className="info-section">
          <label>建议</label>
          {data.recommendations.map((r, i) => <p key={i} className="rec-item">{r}</p>)}
        </div>
      )}
    </div>
  )
}

export const AgentCard: React.FC<Props> = ({ agent }) => {
  const [expanded, setExpanded] = React.useState(true)
  if (agent.status === 'pending') return null

  const renderContent = () => {
    if (!agent.output) return <p className="no-data">暂无输出</p>
    const data = agent.output as Record<string, unknown>
    // LangGraph Agent 节点返回的是 {核心字段, current_agent, ...}，
    // 需要提取嵌套的核心数据字段
    const nested = (key: string) => (data[key] || data) as Record<string, unknown>
    if (agent.name === 'intake' && data.patient_info) {
      const inner = nested('patient_info')
      if (inner && inner.name) return renderPatientInfo(inner as unknown as PatientInfo)
    }
    if (agent.name === 'diagnosis' && data.diagnosis) {
      const inner = nested('diagnosis')
      if (inner && inner.primary_diagnosis) return renderDiagnosis(inner as unknown as DiagnosisData)
    }
    if (agent.name === 'treatment' && data.treatment_plan) {
      const inner = nested('treatment_plan')
      if (inner && inner.diagnosis_addressed) return renderTreatment(inner as unknown as TreatmentData)
    }
    if (agent.name === 'coding' && data.coding_result) {
      const inner = nested('coding_result')
      if (inner && inner.primary_icd10) return renderCoding(inner as unknown as CodingData)
    }
    if (agent.name === 'audit') {
      const inner = nested('audit_result')
      if (inner && inner.compliance_checks) return renderAudit(inner as unknown as AuditData)
    }
    if (data.errors && Array.isArray(data.errors) && data.errors.length > 0) {
      return <p className="error-text">{JSON.stringify(data.errors)}</p>
    }
    return <pre className="json-preview">{JSON.stringify(data, null, 2)}</pre>
  }

  return (
    <div className={`agent-card agent-${agent.name} status-${agent.status}`}>
      <div className="card-header" onClick={() => setExpanded(!expanded)}>
        <div className="card-title">
          <span className={`status-dot ${agent.status}`} />
          <h4>{agent.label}</h4>
        </div>
        <span className="expand-icon">{expanded ? '▼' : '▶'}</span>
      </div>
      {expanded && <div className="card-body">{renderContent()}</div>}
    </div>
  )
}
