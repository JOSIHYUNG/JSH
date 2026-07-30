import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'
import type { ConversationSummary } from '../../domain/knowledge'

type QuestionHistoryPanelProps = {
  conversations: ConversationSummary[]
  onClose: () => void
  onOpen: (id: number) => void
  onRename: (id: number, title: string) => void
  onDelete: (id: number) => void
}

export function QuestionHistoryPanel({ conversations, onClose, onOpen, onRename, onDelete }: QuestionHistoryPanelProps) {
  const requestDelete = (id: number) => {
    if (window.confirm('이 대화와 모든 답변 근거를 삭제할까요?')) onDelete(id)
  }

  const requestRename = (item: ConversationSummary) => {
    const title = window.prompt('대화 제목을 입력하세요.', item.title)?.trim()
    if (title) onRename(item.id, title)
  }

  return (
    <aside className="context-panel history-panel" role="dialog" aria-modal="true" aria-label="대화 기록">
      <div className="panel-topline">
        <div><span className="eyebrow">MEMORY TRACE</span><h2>대화 기록</h2></div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="패널 닫기"><Icon name="close" /></button>
      </div>
      <p className="panel-intro">이전에 내 지식에 물어본 대화와 turn별 근거를 다시 확인합니다.</p>
      <div className="history-list">
        {conversations.map((item) => (
          <div className="history-item" key={item.id}>
            <button className="history-main" type="button" onClick={() => onOpen(item.id)}>
              <div className="history-row"><span className="history-number">{String(item.id).slice(-2)}</span><span className="conversation-status">{item.turn_count} turn</span><time>{new Date(item.last_turn_at ?? item.created_at).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}</time></div>
              <strong>{item.title}</strong>
              <p>{item.title_source === 'auto' ? '첫 질문에서 자동 생성된 대화' : '사용자가 이름을 정한 대화'}</p>
              <small><Icon name="spark" /> 후속 질문을 이어갈 수 있습니다. <Icon name="chevron" /></small>
            </button>
            <div className="history-actions">
              <Button variant="ghost" size="sm" onClick={() => requestRename(item)}><Icon name="edit" /> 이름</Button>
              <Button variant="ghost" size="sm" onClick={() => requestDelete(item.id)}><Icon name="trash" /> 삭제</Button>
            </div>
          </div>
        ))}
      </div>
      {conversations.length === 0 && <div className="small-empty"><Icon name="spark" /><p>아직 대화 기록이 없습니다.</p></div>}
    </aside>
  )
}
