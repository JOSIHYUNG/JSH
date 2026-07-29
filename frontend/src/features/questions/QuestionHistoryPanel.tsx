import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'
import type { QuestionHistorySummary } from '../../domain/knowledge'
import { StatusBadge } from '../feedback/StatusBadge'

export function QuestionHistoryPanel({ history, onClose, onOpen }: { history: QuestionHistorySummary[]; onClose: () => void; onOpen: (id: number) => void }) {
  return <aside className="context-panel history-panel" aria-label="질문 기록"><div className="panel-topline"><div><span className="eyebrow">MEMORY TRACE</span><h2>질문 기록</h2></div><button className="icon-button" type="button" onClick={onClose} aria-label="패널 닫기"><Icon name="close" /></button></div><p className="panel-intro">이전에 내 지식에 물어본 질문과 근거를 다시 확인합니다.</p><div className="history-list">{history.map((item) => <button type="button" key={item.id} onClick={() => onOpen(item.id)}><div className="history-row"><span className="history-number">{String(item.id).slice(-2)}</span><StatusBadge status={item.status} /><time>{new Date(item.created_at).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}</time></div><strong>{item.question_preview}</strong><p>{item.answer_preview ?? '아직 답변이 없습니다.'}</p><small><Icon name="doc" /> 근거 {item.evidence_count}개 <Icon name="chevron" /></small></button>)}</div>{history.length === 0 && <div className="small-empty"><Icon name="spark" /><p>아직 질문 기록이 없습니다.</p></div>}<div className="panel-footer"><Button variant="ghost" size="sm">전체 기록 삭제</Button></div></aside>
}
