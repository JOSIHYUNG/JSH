import { Badge } from '../../components/primitives/Badge'
import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'
import { useState } from 'react'
import type { FormEvent } from 'react'
import type { ConversationDetail, QuestionResult, QuestionSource } from '../../domain/knowledge'
import type { AgentActivityEvent, AgentRunSummary, AgentWebSource } from '../../domain/agent'
import { StatusBadge } from '../feedback/StatusBadge'
import { SourceCard } from './SourceCard'
import { AgentActivityTimeline } from './AgentActivityTimeline'
import { WebSourceCard } from './WebSourceCard'

type ChatPanelProps = {
  conversation: ConversationDetail | null
  latestResult: QuestionResult | null
  onBackToHistory: () => void
  onOpenSource: (source: QuestionSource) => void
  onOpenGeneratedDocument: (id: number) => void
  onAskConcept: (value: string) => void
  onAsk: (value: string) => void
  loading: boolean
  onRetry: (id: number) => void
  onEdit: (question: string) => void
  onNewConversation: () => void
  onRename: (id: number, title: string) => void
  onDelete: (id: number) => void
  agentRun: AgentRunSummary | null
  agentActivities: AgentActivityEvent[]
  onCancelAgent: () => void
  agentWebSources: AgentWebSource[]
  agentQuestion: string | null
}

function renderAnswer(answer: string, webSources: AgentWebSource[]) {
  const normalized = answer.replace(/[\uE000-\uF8FF]cite[\uE000-\uF8FF](S\d+|W\d+)[\uE000-\uF8FF]/g, '[$1]')
  const webSourceMap = new Map(webSources.map((source) => [source.citation_key, source]))
  return normalized.split('\n').map((line, index) => (
    <p key={`${line}-${index}`}>
      {line.split(/(\[(?:S|W)\d+\])/g).map((part, partIndex) => (
        part.match(/^\[(?:S|W)\d+\]$/)
          ? (() => {
            const citationKey = part.slice(1, -1)
            const source = citationKey.startsWith('W') ? webSourceMap.get(citationKey) : null
            if (!source) return <mark key={`${part}-${partIndex}`} className="citation-mark">{part}</mark>
            return (
              <a
                key={`${part}-${partIndex}`}
                className="citation-mark citation-link"
                href={source.url}
                target="_blank"
                rel="noreferrer noopener"
                aria-label={`${citationKey} 웹 출처: ${source.title ?? source.url}`}
              >
                {part}
                <span className="citation-tooltip" role="tooltip">
                  <strong>{source.title ?? 'Web source'}</strong>
                  <span>{source.publisher ?? '웹 검색 출처'}</span>
                  <small>{source.url}</small>
                </span>
              </a>
            )
          })()
          : part
      ))}
    </p>
  ))
}

function Turn({ turn, onOpenSource, onOpenGeneratedDocument, onAskConcept, onRetry, onEdit, agentRun, agentActivities, onCancelAgent, agentWebSources }: { turn: QuestionResult; onOpenSource: (source: QuestionSource) => void; onOpenGeneratedDocument: (id: number) => void; onAskConcept: (value: string) => void; onRetry: (id: number) => void; onEdit: (question: string) => void; agentRun: AgentRunSummary | null; agentActivities: AgentActivityEvent[]; onCancelAgent: () => void; agentWebSources: AgentWebSource[] }) {
  const failed = turn.status === 'failed'
  const noEvidence = turn.status === 'no_evidence'
  const pending = turn.status === 'queued' || turn.status === 'retrieving' || turn.status === 'generating'
  const webSources = turn.web_sources.length > 0 ? turn.web_sources : agentRun?.question_id === turn.id ? agentWebSources : []

  return (
    <article className="chat-turn" aria-label={`대화 ${turn.turn_index ?? ''}번째 질문`}>
      <div className="chat-user-message">
        <span className="chat-turn-label">YOU · TURN {turn.turn_index ?? '—'}</span>
        <p>{turn.question}</p>
      </div>

      {agentRun?.question_id === turn.id && <AgentActivityTimeline events={agentActivities} run={agentRun} onCancel={onCancelAgent} />}
      <div className="chat-assistant-message">
        <div className="chat-turn-heading">
          <Badge tone="violet"><Icon name="spark" /> AI ANSWER</Badge>
          <StatusBadge status={turn.status} />
        </div>

        {pending && (
          <div className="chat-pending" role="status">
            <span className="loading-orbit" />
            <div><strong>{turn.status === 'retrieving' ? '관련 근거를 찾는 중' : turn.status === 'generating' ? '답변을 만드는 중' : '질문을 준비하는 중'}</strong><p>이전 대화의 맥락과 저장된 자료를 함께 확인하고 있습니다.</p></div>
          </div>
        )}

        {noEvidence && (
          <div className="no-evidence chat-no-evidence">
            <span className="empty-orb"><Icon name="search" /></span>
            <h3>관련 자료를 찾지 못했습니다</h3>
            <p>질문을 조금 바꾸거나 자료를 추가해보세요.</p>
          </div>
        )}

        {failed && (
          <div className="answer-failure" role="alert">
            <Icon name="alert" />
            <div><h3>답변을 생성하지 못했습니다</h3><p>{turn.error?.message ?? '잠시 후 다시 시도해 주세요.'}</p></div>
          </div>
        )}

        {!pending && !noEvidence && !failed && (
          <div className="answer-block chat-answer-block">
            <div className="section-label-row"><span className="section-label">GROUNDED ANSWER</span><Badge tone="teal">근거 {turn.sources.length}개</Badge></div>
            <div className="answer-copy">{renderAnswer(turn.answer_markdown ?? '', webSources)}</div>
            <p className="answer-disclaimer"><Icon name="check" /> {turn.answer_mode === 'general' ? '저장된 자료 밖의 일반 AI 답변이며, 아래 AI 문서로 저장했습니다.' : '저장된 자료에만 근거한 답변입니다.'}</p>
          </div>
        )}

        {turn.generated_document && (
          <button type="button" className="generated-document-card" onClick={() => onOpenGeneratedDocument(turn.generated_document?.id ?? 0)}>
            <span className="generated-document-icon"><Icon name="spark" /></span>
            <span className="generated-document-copy"><strong>AI DOCUMENT NODE</strong><span>{turn.generated_document.title}</span><small>그래프와 지식 목록에 추가된 생성 문서 · 열어보기</small></span>
            <Icon name="arrow" />
          </button>
        )}

        {turn.sources.length > 0 && (
          <div className="source-block chat-source-block">
            <div className="section-label-row"><span className="section-label">{failed ? '찾은 근거' : 'REFERENCES'}</span><small>원문 위치로 이동</small></div>
            <div className="source-stack">{turn.sources.map((source) => <SourceCard key={`${turn.id}-${source.citation_key}`} source={source} onOpen={onOpenSource} />)}</div>
          </div>
        )}

        {!pending && turn.related_concepts.length > 0 && (
          <div className="panel-section chat-concepts">
            <div className="section-label-row"><span className="section-label">관련 개념</span><small>{turn.related_concepts.length}</small></div>
            <div className="keyword-list">{turn.related_concepts.map((concept) => <button type="button" className="keyword-chip" key={concept.id} onClick={() => onAskConcept(`${concept.canonical_name}에 대해 저장된 지식으로 설명해줘`)}>{concept.canonical_name} <Icon name="arrow" /></button>)}</div>
          </div>
        )}

        {!pending && (
          <div className="panel-actions chat-turn-actions">
            <Button variant="ghost" size="sm" onClick={() => onRetry(turn.id)}><Icon name="refresh" /> 다시 실행</Button>
            <Button variant="ghost" size="sm" onClick={() => onEdit(turn.question)}>질문 수정</Button>
          </div>
        )}
      </div>
    </article>
  )
}

export function ChatPanel({ conversation, latestResult, onBackToHistory, onOpenSource, onOpenGeneratedDocument, onAskConcept, onAsk, loading, onRetry, onEdit, onNewConversation, onRename, onDelete, agentRun, agentActivities, onCancelAgent, agentWebSources, agentQuestion }: ChatPanelProps) {
  const [draft, setDraft] = useState('')
  const turns = conversation?.turns.length ? conversation.turns : latestResult ? [latestResult] : []
  const summary = conversation?.conversation

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const question = draft.trim()
    if (question.length < 2 || loading) return
    setDraft('')
    onAsk(question)
  }

  const rename = () => {
    if (!summary) return
    const title = window.prompt('대화 제목을 입력하세요.', summary.title)?.trim()
    if (title) onRename(summary.id, title)
  }

  const remove = () => {
    if (summary && window.confirm('이 대화와 모든 답변 근거를 삭제할까요?')) onDelete(summary.id)
  }

  return (
    <aside className="context-panel question-panel chat-panel" role="dialog" aria-modal="true" aria-label="AI 대화">
      <div className="panel-topline">
        <Button variant="ghost" size="sm" onClick={onBackToHistory}>대화 기록</Button>
        <div><Badge tone="violet"><Icon name="spark" /> KNOWLEDGE CHAT</Badge><p className="chat-panel-kicker">{summary ? `${summary.turn_count}개 turn · 근거 기반 대화` : '새 대화'}</p></div>
        <button className="icon-button" type="button" onClick={onBackToHistory} aria-label="대화 기록으로 돌아가기"><Icon name="close" /></button>
      </div>
      <div className="chat-panel-heading">
        <div><span className="section-label">CONVERSATION</span><h2>{summary?.title ?? '지식에게 질문하기'}</h2></div>
        <div className="panel-actions"><Button variant="ghost" size="sm" onClick={onNewConversation}><Icon name="plus" /> 새 대화</Button>{summary && <><Button variant="ghost" size="sm" onClick={rename}>이름 수정</Button><Button variant="ghost" size="sm" onClick={remove}><Icon name="trash" /> 삭제</Button></>}</div>
      </div>
      {agentWebSources.length > 0 && <section className="source-block web-source-block"><div className="section-label-row"><span className="section-label">WEB SOURCES</span><small>Agent가 참고한 외부 출처</small></div><div className="source-stack">{agentWebSources.map((source) => <WebSourceCard key={source.citation_key} source={source} />)}</div></section>}
      <div className="chat-thread" aria-live="polite">
        {turns.map((turn) => <Turn key={turn.id} turn={turn} onOpenSource={onOpenSource} onOpenGeneratedDocument={onOpenGeneratedDocument} onAskConcept={onAskConcept} onRetry={onRetry} onEdit={onEdit} agentRun={agentRun} agentActivities={agentActivities} onCancelAgent={onCancelAgent} agentWebSources={agentWebSources} />)}
        {agentRun && agentQuestion && !turns.some((turn) => turn.id === agentRun.question_id) && <article className="chat-turn chat-current-agent-turn"><div className="chat-user-message"><span className="chat-turn-label">YOU · NEW QUESTION</span><p>{agentQuestion}</p></div><AgentActivityTimeline events={agentActivities} run={agentRun} onCancel={onCancelAgent} /></article>}
        {!turns.length && <div className="chat-pending" role="status"><span className="loading-orbit" /><div><strong>Agent가 질문을 분석하고 있습니다.</strong><p>필요한 지식과 연결 관계를 순서대로 탐색합니다.</p></div></div>}
      </div>
      <form className="chat-composer" onSubmit={submit}>
        <span className="section-label">FOLLOW-UP QUESTION</span>
        <div className="chat-composer-input">
          <Icon name="search" label="후속 질문" />
          <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="이 대화에 이어서 질문하세요" aria-label="후속 질문" disabled={loading} />
          <Button variant="primary" type="submit" disabled={loading || draft.trim().length < 2}>{loading ? '답변 중…' : '보내기'} <Icon name="arrow" /></Button>
        </div>
        <p>이전 turn은 맥락으로 참고하고, 새 답변은 새 근거를 검색합니다.</p>
      </form>
    </aside>
  )
}
