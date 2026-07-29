import { Badge } from '../../components/primitives/Badge'
import { Icon } from '../../components/primitives/Icon'
import type { QuestionResult, QuestionSource } from '../../domain/knowledge'
import { StatusBadge } from '../feedback/StatusBadge'
import { SourceCard } from './SourceCard'

function renderAnswer(answer: string) {
  return answer.split('\n').map((line, index) => <p key={`${line}-${index}`}>{line.split(/(\[S\d\])/g).map((part, partIndex) => part.match(/^\[S\d\]$/) ? <mark key={`${part}-${partIndex}`} className="citation-mark">{part}</mark> : part)}</p>)
}

export function QuestionResultPanel({ result, onClose, onOpenSource, onAskConcept }: { result: QuestionResult; onClose: () => void; onOpenSource: (source: QuestionSource) => void; onAskConcept: (value: string) => void }) {
  const noEvidence = result.status === 'no_evidence' || result.sources.length === 0
  return <aside className="context-panel question-panel" aria-label="AI 질문 결과"><div className="panel-topline"><Badge tone="violet"><Icon name="spark" /> AI SYNTHESIS</Badge><button className="icon-button" type="button" onClick={onClose} aria-label="패널 닫기"><Icon name="close" /></button></div><div className="question-result-heading"><span className="section-label">YOUR QUESTION</span><h2>{result.question}</h2><StatusBadge status={result.status} /></div>{noEvidence ? <div className="no-evidence"><span className="empty-orb"><Icon name="search" /></span><h3>관련 자료를 찾지 못했습니다</h3><p>저장된 지식 안에서 충분한 근거가 없어요. 질문을 조금 바꾸거나 자료를 추가해보세요.</p></div> : <><div className="answer-block"><div className="section-label-row"><span className="section-label">GROUNDED ANSWER</span><Badge tone="teal">근거 {result.sources.length}개</Badge></div><div className="answer-copy">{renderAnswer(result.answer_markdown ?? '')}</div><p className="answer-disclaimer"><Icon name="check" /> 저장된 자료에만 근거한 답변입니다.</p></div><div className="source-block"><div className="section-label-row"><span className="section-label">REFERENCES</span><small>원문 위치로 이동</small></div><div className="source-stack">{result.sources.map((source) => <SourceCard key={source.citation_key} source={source} onOpen={onOpenSource} />)}</div></div><div className="panel-section"><div className="section-label-row"><span className="section-label">관련 개념</span><small>{result.related_concepts.length}</small></div><div className="keyword-list">{result.related_concepts.map((concept) => <button type="button" className="keyword-chip" key={concept.id} onClick={() => onAskConcept(`${concept.canonical_name}에 대해 저장된 지식으로 설명해줘`)}>{concept.canonical_name} <Icon name="arrow" /></button>)}</div></div></>}</aside>
}
