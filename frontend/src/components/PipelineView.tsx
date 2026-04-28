import React from 'react'
import type { AgentStatus } from '../types'

interface Props {
  agents: AgentStatus[]
  loading: boolean
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#4a5568',
  running: '#3182ce',
  done: '#38a169',
}

const AGENT_ICONS: Record<string, string> = {
  intake: '📋',
  diagnosis: '🔍',
  treatment: '💊',
  coding: '🏷️',
  audit: '🛡️',
}

export const PipelineView: React.FC<Props> = ({ agents, loading }) => {
  return (
    <div className="pipeline-view">
      <h3>Pipeline 执行状态</h3>
      <div className="pipeline-flow">
        {agents.map((agent, i) => (
          <React.Fragment key={agent.name}>
            {i > 0 && (
              <div className="pipeline-arrow">
                <div className={`arrow-line ${loading && agents[i - 1].status === 'done' ? 'active' : ''}`} />
                <span className="arrow-head">→</span>
              </div>
            )}
            <div
              className={`pipeline-node ${agent.status}`}
              style={{ borderColor: STATUS_COLORS[agent.status] }}
            >
              <span className="node-icon">{AGENT_ICONS[agent.name]}</span>
              <span className="node-label">{agent.label}</span>
              <span
                className="node-status"
                style={{ background: STATUS_COLORS[agent.status] }}
              >
                {agent.status === 'pending' ? '等待' : agent.status === 'running' ? '执行中' : '完成'}
              </span>
              {agent.status === 'running' && <div className="spinner" />}
            </div>
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}
