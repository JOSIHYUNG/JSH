import type { AgentActivityEvent, AgentRunSummary } from '../../domain/agent'
import { Icon } from '../../components/primitives/Icon'

function iconFor(event: AgentActivityEvent): 'search' | 'alert' | 'check' | 'orbit' {
  if (event.status === 'failed' || event.type === 'run_failed') return 'alert'
  if (event.type === 'run_completed') return 'check'
  if (event.tool === 'explore_node') return 'orbit'
  if (event.tool === 'web_search') return 'search'
  return 'search'
}

function phaseFor(run: AgentRunSummary | null, events: AgentActivityEvent[]) {
  if (!run) return { label: '질문을 준비하고 있습니다.', icon: 'search' as const }
  if (run.status === 'queued') return { label: '질문을 준비하고 있습니다.', icon: 'search' as const }
  if (run.status === 'completed') return { label: '답변을 정리했습니다.', icon: 'check' as const }
  if (run.status === 'failed') return { label: '답변 생성에 실패했습니다.', icon: 'alert' as const }
  if (run.status === 'canceled') return { label: 'Agent 실행을 중단했습니다.', icon: 'alert' as const }
  if (run.status === 'max_turns') return { label: '탐색 한도에 도달했습니다.', icon: 'alert' as const }
  const latest = events[events.length - 1]
  if (latest?.tool === 'web_search') return { label: '최신 웹 자료를 검색하고 있습니다.', icon: 'search' as const }
  if (latest?.tool === 'explore_node') return { label: '연결된 개념을 탐색하고 있습니다.', icon: 'orbit' as const }
  if (latest?.tool === 'search_knowledge') return { label: '저장된 자료를 찾고 있습니다.', icon: 'search' as const }
  if (latest?.type === 'model_started' && events.some((event) => event.tool)) return { label: '찾은 근거를 바탕으로 답변을 작성하고 있습니다.', icon: 'spark' as const }
  if (run.stage === 'finalizing') return { label: '찾은 근거를 바탕으로 답변을 작성하고 있습니다.', icon: 'spark' as const }
  return { label: '질문을 생각하고 있습니다.', icon: 'spark' as const }
}

function eventLabel(event: AgentActivityEvent) {
  if (event.type === 'run_started') return '질문을 분석하기 시작했습니다.'
  if (event.type === 'model_started') return '답변 방향을 생각하고 있습니다.'
  if (event.type === 'run_completed') return '답변을 정리했습니다.'
  if (event.type === 'run_failed') return '답변 생성에 실패했습니다.'
  if (event.type === 'run_canceled') return 'Agent 실행을 중단했습니다.'
  if (event.tool === 'web_search') return event.status === 'started' ? '최신 웹 자료를 검색하고 있습니다.' : '웹 검색 결과를 반영했습니다.'
  if (event.tool === 'explore_node') return event.status === 'started' ? '연결된 개념을 탐색하고 있습니다.' : '개념 탐색 결과를 반영했습니다.'
  if (event.tool === 'search_knowledge') return event.status === 'started' ? '저장된 자료를 찾고 있습니다.' : '저장된 자료를 확인했습니다.'
  return event.label ?? 'Agent가 답변을 준비하고 있습니다.'
}

export function AgentActivityTimeline({ events, run, onCancel }: { events: AgentActivityEvent[]; run: AgentRunSummary | null; onCancel?: () => void }) {
  if (!run && events.length === 0) return null
  const terminal = run && ['completed', 'failed', 'canceled', 'max_turns'].includes(run.status)
  const phase = phaseFor(run, events)
  return (
    <section className="agent-activity" aria-live="polite" aria-label="Agent 탐색 활동">
      <div className="agent-activity-heading">
        <div><span className="section-label">AGENT TRACE</span><strong>{terminal ? '탐색이 종료되었습니다' : '관련 지식을 탐색하고 있습니다'}</strong></div>
        {run && !terminal && onCancel && <button type="button" className="agent-cancel" onClick={onCancel}>중단</button>}
      </div>
      <div className={`agent-current-phase ${terminal ? 'is-terminal' : 'is-running'}`} role="status">
        <span className="agent-phase-icon"><Icon name={phase.icon} /></span>
        <span>{phase.label}</span>
        {!terminal && <span className="agent-phase-dots" aria-hidden="true">•••</span>}
      </div>
      <ol className="agent-activity-list">
        {events.map((event) => (
          <li key={event.sequence} className={`agent-activity-item is-${event.status ?? 'completed'}`}>
            <span className="agent-activity-icon"><Icon name={iconFor(event)} /></span>
            <span className="agent-activity-copy"><span>{eventLabel(event)}</span>{event.query_preview && <small>{event.query_preview}</small>}</span>
            {event.result_count !== null && <small className="agent-activity-count">{event.result_count}</small>}
          </li>
        ))}
        {!events.length && <li className="agent-activity-empty"><span className="loading-orbit" /> Agent가 탐색을 준비하고 있습니다.</li>}
      </ol>
    </section>
  )
}
