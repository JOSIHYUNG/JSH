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
}

export function DocumentPanel({ document, onClose, onOpenConcept, onAskConcept }: DocumentPanelProps) {
  return <aside className="context-panel" aria-label="문서 상세">
    <div className="panel-topline"><Badge tone="amber"><Icon name="doc" /> DOCUMENT</Badge><button className="icon-button" type="button" onClick={onClose} aria-label="패널 닫기"><Icon name="close" /></button></div>
    <div className="panel-heading"><h2>{document.title}</h2><StatusBadge status={document.status} /></div>
    <p className="panel-meta">{document.filename ?? '직접 입력'} · {document.character_count.toLocaleString()}자 · {document.chunk_count} chunks</p>
    <div className="panel-section"><span className="section-label">핵심 요약</span><p className="panel-summary">{document.summary}</p></div>
    <div className="panel-section"><span className="section-label">KEYWORDS</span><div className="keyword-list">{document.keywords.map((keyword) => <span key={keyword}>{keyword}</span>)}</div></div>
    <div className="panel-section"><div className="section-label-row"><span className="section-label">연결된 개념</span><small>{document.concepts.length}개</small></div><div className="concept-list">{document.concepts.map((concept) => <button type="button" key={concept.id} onClick={() => onOpenConcept(concept.id)}><ConceptBadge type={concept.concept_type} /><strong>{concept.canonical_name}</strong><Icon name="chevron" /></button>)}</div></div>
    <div className="panel-section"><div className="section-label-row"><span className="section-label">원문 미리보기</span><Button variant="ghost" size="sm" onClick={() => onAskConcept(`「${document.title}」의 핵심 내용을 정리해줘`)}>이 자료로 질문</Button></div><article className="original-preview">{document.original_content}</article></div>
  </aside>
}
