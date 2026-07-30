import { useEffect, useState } from 'react'
import { Button } from '../../components/primitives/Button'
import { Badge } from '../../components/primitives/Badge'
import { Icon } from '../../components/primitives/Icon'
import type { DocumentDetail } from '../../domain/knowledge'
import { StatusBadge } from '../feedback/StatusBadge'
import { ConceptBadge } from '../concepts/ConceptBadge'

type DocumentPanelProps = {
  document: DocumentDetail
  onClose: () => void
  onOpenConcept: (id: number) => void
  onAskConcept: (value: string) => void
  onDelete: (id: number) => void
  onReanalyze: (id: number) => void
  onUpdate: (id: number, payload: { title?: string; content?: string }) => Promise<boolean>
  onOpenFullDocument: (id: number) => void
}

export function DocumentPanel({ document, onClose, onOpenConcept, onAskConcept, onDelete, onReanalyze, onUpdate, onOpenFullDocument }: DocumentPanelProps) {
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [draftTitle, setDraftTitle] = useState(document.title)
  const [draftContent, setDraftContent] = useState(document.original_content)

  useEffect(() => {
    setEditing(false)
    setDraftTitle(document.title)
    setDraftContent(document.original_content)
  }, [document.id, document.original_content, document.title])

  const requestDelete = () => { if (window.confirm('이 자료를 그래프와 새로운 AI 답변에서 제외할까요?')) onDelete(document.id) }
  const startEditing = () => {
    if (document.original_range) {
      onOpenFullDocument(document.id)
      return
    }
    setEditing(true)
  }
  const cancelEditing = () => { setEditing(false); setDraftTitle(document.title); setDraftContent(document.original_content) }
  const saveEditing = async () => {
    const payload: { title?: string; content?: string } = {}
    if (draftTitle.trim() !== document.title) payload.title = draftTitle.trim()
    if (draftContent !== document.original_content) payload.content = draftContent
    if (!payload.title && payload.content === undefined) { setEditing(false); return }
    setSaving(true)
    const saved = await onUpdate(document.id, payload)
    setSaving(false)
    if (saved) setEditing(false)
  }
  const range = document.original_range
  const highlightedOriginal = range && range.highlight_start_char !== null && range.highlight_end_char !== null
    ? <>{document.original_content.slice(0, range.highlight_start_char)}<mark className="source-highlight">{document.original_content.slice(range.highlight_start_char, range.highlight_end_char)}</mark>{document.original_content.slice(range.highlight_end_char)}</>
    : document.original_content

  return <aside className="context-panel" role="dialog" aria-modal="true" aria-label="문서 상세">
    <div className="panel-topline"><Badge tone="amber"><Icon name="doc" /> DOCUMENT</Badge><button className="icon-button" type="button" onClick={onClose} aria-label="패널 닫기"><Icon name="close" /></button></div>
    {editing ? <form className="document-edit-form" onSubmit={(event) => { event.preventDefault(); void saveEditing() }}>
      <label className="field-label">제목<input value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} maxLength={255} /></label>
      <label className="field-label">본문<textarea value={draftContent} onChange={(event) => setDraftContent(event.target.value)} rows={15} /></label>
      <div className="panel-actions"><Button type="button" variant="ghost" size="sm" onClick={cancelEditing}>취소</Button><Button type="submit" variant="primary" size="sm" disabled={saving || !draftTitle.trim() || draftContent.trim().length < 1}>{saving ? '저장 중…' : '변경 저장'} <Icon name="check" /></Button></div>
    </form> : <>
      <div className="panel-heading"><h2>{document.title}</h2><StatusBadge status={document.status} /></div>
      <p className="panel-meta">{document.filename ?? '직접 입력'} · {document.character_count.toLocaleString()}자 · {document.chunk_count} chunks</p>
      <div className="panel-actions document-actions"><Button variant="ghost" size="sm" onClick={startEditing} disabled={document.status === 'processing' || document.status === 'deleting'}><Icon name="edit" /> {document.original_range ? '전체 원문 편집' : '자료 수정'}</Button><Button variant="ghost" size="sm" onClick={() => onReanalyze(document.id)} disabled={document.status === 'processing' || document.status === 'deleting'}><Icon name="refresh" /> 다시 분석</Button><Button variant="danger" size="sm" onClick={requestDelete} disabled={document.status === 'deleting'}><Icon name="trash" /> 자료 삭제</Button></div>
      <div className="panel-section"><span className="section-label">핵심 요약</span><p className="panel-summary">{document.summary}</p></div>
      <div className="panel-section"><span className="section-label">KEYWORDS</span><div className="keyword-list">{document.keywords.map((keyword) => <span key={keyword}>{keyword}</span>)}</div></div>
      <div className="panel-section"><div className="section-label-row"><span className="section-label">연결된 개념</span><small>{document.concepts.length}개</small></div><div className="concept-list">{document.concepts.map((concept) => <button type="button" key={concept.id} onClick={() => onOpenConcept(concept.id)}><ConceptBadge type={concept.concept_type} /><strong>{concept.canonical_name}</strong><Icon name="chevron" /></button>)}</div></div>
      <div className="panel-section"><div className="section-label-row"><span className="section-label">원문 미리보기</span><Button variant="ghost" size="sm" onClick={() => onAskConcept(`「${document.title}」의 핵심 내용을 정리해줘`)}>이 자료로 질문</Button></div><article className="original-preview">{highlightedOriginal}</article></div>
    </>}
  </aside>
}
