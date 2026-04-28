import { useState, useCallback, useRef } from 'react'
import type { AgentEvent, AgentStatus } from '../types'

const AGENT_LABELS: Record<string, string> = {
  intake: '接诊 Agent',
  diagnosis: '诊断 Agent',
  treatment: '治疗 Agent',
  coding: '编码 Agent',
  audit: '审计 Agent',
}

const INITIAL_AGENTS: AgentStatus[] = [
  { name: 'intake', label: '接诊 Agent', status: 'pending' },
  { name: 'diagnosis', label: '诊断 Agent', status: 'pending' },
  { name: 'treatment', label: '治疗 Agent', status: 'pending' },
  { name: 'coding', label: '编码 Agent', status: 'pending' },
  { name: 'audit', label: '审计 Agent', status: 'pending' },
]

export function useClinicalPipeline() {
  const [loading, setLoading] = useState(false)
  const [agents, setAgents] = useState<AgentStatus[]>(INITIAL_AGENTS)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const runPipeline = useCallback(async (patientDescription: string) => {
    setLoading(true)
    setError(null)
    setAgents(INITIAL_AGENTS.map(a => ({ ...a, status: 'pending' as const })))

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await fetch('/api/v1/clinical/analyze/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_description: patientDescription,
          thread_id: crypto.randomUUID(),
        }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('浏览器不支持流式响应')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue

          try {
            const event: AgentEvent = JSON.parse(trimmed.slice(6))
            if (event.agent && event.output) {
              setAgents(prev =>
                prev.map(a =>
                  a.name === event.agent
                    ? { ...a, status: 'done' as const, output: event.output }
                    : a.status === 'done'
                    ? a
                    : a.name < event.agent!
                    ? { ...a, status: 'done' as const }
                    : a
                )
              )
            }
            if (event.complete) {
              setAgents(prev => prev.map(a => ({ ...a, status: 'done' as const })))
            }
          } catch {
            // skip unparseable lines
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : '分析请求失败')
    } finally {
      setLoading(false)
    }
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setLoading(false)
  }, [])

  return { loading, agents, error, runPipeline, cancel }
}
