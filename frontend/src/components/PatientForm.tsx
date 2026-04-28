import React from 'react'

interface Props {
  onSubmit: (text: string) => void
  loading: boolean
  onCancel: () => void
}

const EXAMPLE = `45岁男性，发热（39.2°C）3天，咳黄痰伴右侧胸痛。既往史：2型糖尿病、高血压。当前用药：二甲双胍500mg 每日两次，赖诺普利10mg 每日一次。过敏史：青霉素（皮疹）。实验室检查：WBC 15,000/μL，CRP 85 mg/L，胸部X线示右肺下叶浸润。`

export const PatientForm: React.FC<Props> = ({ onSubmit, loading, onCancel }) => {
  const [text, setText] = React.useState('')
  const [showExample, setShowExample] = React.useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const input = text.trim() || EXAMPLE
    if (input.length < 10) return
    onSubmit(input)
  }

  const fillExample = () => {
    setText(EXAMPLE)
    setShowExample(false)
  }

  return (
    <form className="patient-form" onSubmit={handleSubmit}>
      <div className="form-header">
        <h2>患者信息录入</h2>
        {!loading && (
          <button
            type="button"
            className="btn-example"
            onClick={() => setShowExample(!showExample)}
          >
            {showExample ? '收起示例' : '加载示例'}
          </button>
        )}
      </div>

      {showExample && (
        <div className="example-card" onClick={fillExample}>
          <strong>示例患者（点击填充）：</strong>
          <p>{EXAMPLE}</p>
        </div>
      )}

      <textarea
        className="patient-input"
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder={showExample ? '' : '请输入患者临床描述（症状、既往史、用药、过敏史、检查结果等）...\n\n或点击右上角「加载示例」使用内置病例'}
        rows={8}
        disabled={loading}
      />

      <div className="form-actions">
        <span className="char-count">{text.length} / 5000 字符</span>
        {loading ? (
          <button type="button" className="btn-cancel" onClick={onCancel}>
            取消分析
          </button>
        ) : (
          <button type="submit" className="btn-submit" disabled={text.trim().length < 10 && !text}>
            开始分析
          </button>
        )}
      </div>
    </form>
  )
}
