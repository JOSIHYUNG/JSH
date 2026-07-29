import { useState } from 'react'
import type { FormEvent } from 'react'
import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'

export function QuestionBar({ loading, onSubmit, initialValue = '' }: { loading: boolean; onSubmit: (question: string) => void; initialValue?: string }) {
  const [value, setValue] = useState(initialValue)
  const submit = (event: FormEvent) => { event.preventDefault(); if (value.trim().length >= 2 && !loading) onSubmit(value.trim()) }
  return <form className="question-bar" onSubmit={submit}><div className="question-prompt"><span className="question-icon"><Icon name="spark" /></span><div><span className="eyebrow">ASK YOUR KNOWLEDGE</span><h2>내 지식에게 질문하세요</h2></div></div><div className="question-input-wrap"><Icon name="search" label="질문" /><input value={value} onChange={(event) => setValue(event.target.value)} placeholder="키워드나 문장으로 물어보세요" aria-label="내 지식에게 질문" /><Button variant="primary" type="submit" disabled={loading || value.trim().length < 2}>{loading ? '답변 만드는 중…' : 'AI에게 질문'} <Icon name="arrow" /></Button></div><p className="question-hint">저장된 자료에서 근거를 찾아 답변하고, 참고 문서 위치까지 연결합니다.</p></form>
}
