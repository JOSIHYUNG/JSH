import { useState } from 'react'
import type { FormEvent } from 'react'
import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'
import type { ConversationSummary } from '../../domain/knowledge'

export function QuestionBar({ loading, onSubmit, initialValue = '', value, onValueChange, activeConversation, onNewConversation }: { loading: boolean; onSubmit: (question: string) => void; initialValue?: string; value?: string; onValueChange?: (value: string) => void; activeConversation?: ConversationSummary | null; onNewConversation?: () => void }) {
  const [internalValue, setInternalValue] = useState(initialValue)
  const currentValue = value ?? internalValue
  const submit = (event: FormEvent) => { event.preventDefault(); if (currentValue.trim().length >= 2 && !loading) onSubmit(currentValue.trim()) }
  return <form className="question-bar" onSubmit={submit}><div className="question-prompt"><span className="question-icon"><Icon name="spark" /></span><div><span className="eyebrow">{activeConversation ? 'CONTINUE KNOWLEDGE CHAT' : 'ASK YOUR KNOWLEDGE'}</span><h2>{activeConversation ? activeConversation.title : '내 지식에게 질문하세요'}</h2></div>{activeConversation && onNewConversation && <Button variant="ghost" size="sm" type="button" onClick={onNewConversation}><Icon name="plus" /> 새 대화</Button>}</div><div className="question-input-wrap"><Icon name="search" label="질문" /><input value={currentValue} onChange={(event) => { const next = event.target.value; setInternalValue(next); onValueChange?.(next) }} placeholder={activeConversation ? '이 대화에 이어서 질문하세요' : '키워드나 문장으로 물어보세요'} aria-label={activeConversation ? '후속 질문' : '내 지식에게 질문'} /><Button variant="primary" type="submit" disabled={loading || currentValue.trim().length < 2}>{loading ? '답변 만드는 중…' : activeConversation ? '후속 질문' : 'AI에게 질문'} <Icon name="arrow" /></Button></div><p className="question-hint">이전 대화의 맥락을 참고하고, 매 답변마다 새 근거와 참고 문서 위치를 연결합니다.</p></form>
}
