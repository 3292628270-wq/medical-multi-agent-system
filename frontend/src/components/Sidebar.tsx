import React, { useState } from 'react'

export const Sidebar: React.FC = () => {
  const [icdQuery, setIcdQuery] = useState('')
  const [icdResults, setIcdResults] = useState<Array<{ code: string; description: string; category: string }>>([])
  const [icdSearching, setIcdSearching] = useState(false)

  const [newDrug, setNewDrug] = useState('')
  const [currentDrugs, setCurrentDrugs] = useState('')
  const [ddiResults, setDdiResults] = useState<Array<{
    drug_a: string; drug_b: string; severity: string
    description: string; recommendation: string
  }>>([])
  const [ddiSearching, setDdiSearching] = useState(false)

  const searchICD10 = async () => {
    if (!icdQuery.trim()) return
    setIcdSearching(true)
    try {
      const res = await fetch('/api/v1/clinical/icd10/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: icdQuery }),
      })
      const data = await res.json()
      setIcdResults(data.results || [])
    } catch {
      setIcdResults([])
    } finally {
      setIcdSearching(false)
    }
  }

  const checkDDI = async () => {
    if (!newDrug.trim()) return
    setDdiSearching(true)
    try {
      const res = await fetch('/api/v1/clinical/ddi/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          new_drugs: newDrug.split(',').map(d => d.trim()).filter(Boolean),
          current_drugs: currentDrugs.split(',').map(d => d.trim()).filter(Boolean),
        }),
      })
      const data = await res.json()
      setDdiResults(data.interactions || [])
    } catch {
      setDdiResults([])
    } finally {
      setDdiSearching(false)
    }
  }

  return (
    <aside className="sidebar">
      {/* ICD-10 搜索 */}
      <div className="sidebar-card">
        <h4>🏷️ ICD-10 编码搜索</h4>
        <div className="sidebar-search">
          <input
            value={icdQuery}
            onChange={e => setIcdQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && searchICD10()}
            placeholder="搜索疾病名或编码..."
          />
          <button onClick={searchICD10} disabled={icdSearching}>搜索</button>
        </div>
        {icdResults.length > 0 && (
          <ul className="sidebar-results">
            {icdResults.map((r, i) => (
              <li key={i}>
                <span className="code">{r.code}</span>
                <span className="desc">{r.description}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* DDI 检查 */}
      <div className="sidebar-card">
        <h4>💊 药物相互作用</h4>
        <div className="sidebar-search">
          <input
            value={newDrug}
            onChange={e => setNewDrug(e.target.value)}
            placeholder="新开药物（逗号分隔）"
          />
          <input
            value={currentDrugs}
            onChange={e => setCurrentDrugs(e.target.value)}
            placeholder="当前用药（逗号分隔）"
          />
          <button onClick={checkDDI} disabled={ddiSearching}>检查</button>
        </div>
        {ddiResults.length > 0 && (
          <ul className="sidebar-results ddi">
            {ddiResults.map((r, i) => (
              <li key={i} className={`severity-${r.severity}`}>
                <div className="ddi-pair">{r.drug_a} + {r.drug_b}</div>
                <span className={`badge ${r.severity}`}>{r.severity}</span>
                <p>{r.recommendation}</p>
              </li>
            ))}
          </ul>
        )}
        {ddiResults.length === 0 && !ddiSearching && (newDrug || currentDrugs) && (
          <p className="no-result">未发现已知相互作用</p>
        )}
      </div>
    </aside>
  )
}
