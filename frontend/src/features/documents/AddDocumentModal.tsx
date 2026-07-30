import { useEffect, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'
import { Badge } from '../../components/primitives/Badge'
import type { AnalysisProgress } from '../../hooks/useKnowledgeController'
import type { DocumentSummary } from '../../domain/knowledge'
import { ErrorState } from '../feedback/ErrorState'

const analysisSteps = ['원문 저장', '내용 구조화', '개념 연결', '그래프 반영']

type AddDocumentModalProps = {
  open: boolean
  loading: boolean
  progress: AnalysisProgress | null
  error: string | null
  cancelAvailable: boolean
  onClose: () => void
  onSubmit: (title: string, content: string, file?: File) => Promise<DocumentSummary | null>
  onCancelAnalysis: () => void
  onViewDocument: (id: number) => void
}

function getStepIndex(progress: AnalysisProgress | null): number {
  if (!progress) return 0
  if (progress.stage === 'extracting_concepts' || progress.stage === 'linking_concepts') return 2
  if (progress.stage === 'finalizing' || progress.stage === 'completed') return 3
  if (progress.stage === 'chunking' || progress.stage === 'summarizing') return 1
  return 0
}

export function AddDocumentModal({ open, loading, progress, error, cancelAvailable, onClose, onSubmit, onCancelAnalysis, onViewDocument }: AddDocumentModalProps) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [mode, setMode] = useState<'paste' | 'upload'>('paste')
  const [submitted, setSubmitted] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [createdDocumentId, setCreatedDocumentId] = useState<number | null>(null)

  useEffect(() => {
    if (!open) {
      setTitle('')
      setContent('')
      setMode('paste')
      setSubmitted(false)
      setSelectedFile(null)
      setCreatedDocumentId(null)
    }
  }, [open])

  if (!open) return null

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setSelectedFile(file)
    if (file.type === 'text/plain' || file.type === 'text/markdown' || /\.(txt|md)$/i.test(file.name)) {
      const reader = new FileReader()
      reader.onload = () => setContent(String(reader.result ?? ''))
      reader.readAsText(file)
    } else {
      setContent('')
    }
  }

  const canSubmit = mode === 'upload' ? Boolean(selectedFile) : content.trim().length >= 2
  const currentStep = getStepIndex(progress)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!canSubmit || loading) return
    setSubmitted(true)
    const result = await onSubmit(title.trim(), content.trim(), mode === 'upload' ? selectedFile ?? undefined : undefined)
    if (result) {
      setCreatedDocumentId(result.id)
      setSubmitted(true)
    }
    else setSubmitted(false)
  }

  return <div className="modal-layer" role="presentation">
    <div className="modal-backdrop" onClick={onClose} />
    <section className="add-modal" role="dialog" aria-modal="true" aria-labelledby="add-document-title">
      <div className="modal-header">
        <div><span className="eyebrow">INGEST / NEW MEMORY</span><h2 id="add-document-title">자료를 지식으로 바꾸기</h2></div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="닫기"><Icon name="close" /></button>
      </div>
      {!submitted && <form onSubmit={submit}>
        <div className="mode-tabs">
          <button type="button" className={mode === 'paste' ? 'is-active' : ''} onClick={() => { setMode('paste'); setSelectedFile(null) }}><Icon name="doc" /> 텍스트 입력</button>
          <label className={`mode-tab ${mode === 'upload' ? 'is-active' : ''}`}><input type="file" accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf" onChange={(event) => { setMode('upload'); handleFile(event) }} /><Icon name="plus" /> 파일 업로드</label>
        </div>
        <label className="field-label">제목<span>선택 · 비우면 분석 결과로 자동 지정</span><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="자료의 제목을 입력하세요" /></label>
        {mode === 'paste' && <label className="field-label">본문<span>필수</span><textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="메모, 업무자료, 읽은 내용 등의 텍스트를 붙여 넣으세요." rows={9} autoFocus /></label>}
        {selectedFile && <div className="file-note"><Icon name="check" /> {selectedFile.name} 파일이 선택되었습니다.</div>}
        {mode === 'upload' && !selectedFile && <div className="upload-empty"><Icon name="plus" /><p>위의 파일 업로드 버튼에서 .txt, .md 또는 텍스트 추출 가능한 .pdf를 선택하세요.</p></div>}
        <div className="ai-notice"><span className="notice-icon"><Icon name="spark" /></span><p>분석을 시작하면 원문을 저장하고 AI 분석 결과를 지식 그래프에 반영합니다.</p></div>
        {error && <ErrorState title="자료를 처리하지 못했습니다" message={error} />}
        <div className="modal-actions"><Button type="button" variant="ghost" onClick={onClose}>취소</Button><Button type="submit" variant="primary" disabled={!canSubmit}>분석 시작 <Icon name="arrow" /></Button></div>
      </form>}
      {submitted && <div className="analysis-progress" aria-live="polite">
        <div className="analysis-orbit"><span className="orbit-core"><Icon name="spark" /></span><span className="orbit-ring ring-one" /><span className="orbit-ring ring-two" /></div>
        <Badge tone="teal">{loading ? 'ANALYSIS RUNNING' : 'ANALYSIS COMPLETE'}</Badge>
        <h3>{loading ? (progress?.message || '자료를 분석하고 연결하는 중입니다') : '분석이 완료되었습니다'}</h3>
        <p>{loading ? `진행률 ${progress?.progress ?? 0}% · 모달을 닫아도 원문은 보존되고 분석은 계속됩니다.` : '자료가 그래프와 로컬 검색에 반영되었습니다. 외부 의미 검색 인덱스는 별도로 동기화될 수 있습니다.'}</p>
        <div className="analysis-steps">{analysisSteps.map((item, index) => <div className={!loading || index < currentStep ? 'is-done' : index === currentStep ? 'is-current' : ''} key={item}><span>{!loading || index < currentStep ? <Icon name="check" /> : index + 1}</span><label>{item}</label></div>)}</div>
        {loading && <div className="modal-actions"><Button variant="ghost" onClick={onClose}>백그라운드에서 계속</Button><Button variant="danger" onClick={onCancelAnalysis} disabled={!cancelAvailable}>분석 취소</Button></div>}
        {!loading && createdDocumentId && <div className="modal-actions"><Button variant="ghost" onClick={onClose}>닫기</Button><Button variant="primary" onClick={() => onViewDocument(createdDocumentId)}>문서와 그래프에서 보기 <Icon name="arrow" /></Button></div>}
      </div>}
    </section>
  </div>
}
