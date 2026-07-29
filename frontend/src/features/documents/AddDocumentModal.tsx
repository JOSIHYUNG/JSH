import { useEffect, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'
import { Badge } from '../../components/primitives/Badge'

const analysisSteps = ['원문 저장', '내용 구조화', '개념 연결', '그래프 반영']

type AddDocumentModalProps = {
  open: boolean
  loading: boolean
  onClose: () => void
  onSubmit: (title: string, content: string, file?: File) => Promise<unknown>
}

export function AddDocumentModal({ open, loading, onClose, onSubmit }: AddDocumentModalProps) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [mode, setMode] = useState<'paste' | 'upload'>('paste')
  const [submitted, setSubmitted] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  useEffect(() => {
    if (!open) {
      setTitle('')
      setContent('')
      setMode('paste')
      setSubmitted(false)
      setSelectedFile(null)
    }
  }, [open])

  if (!open) return null

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setSelectedFile(file)
    setTitle(file.name.replace(/\.[^/.]+$/, ''))
    if (file.type === 'text/plain' || file.type === 'text/markdown' || /\.(txt|md)$/i.test(file.name)) {
      const reader = new FileReader()
      reader.onload = () => setContent(String(reader.result ?? ''))
      reader.readAsText(file)
    } else {
      setContent(file.name)
    }
  }

  const canSubmit = Boolean(title.trim()) && (Boolean(selectedFile) || content.trim().length >= 2)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!canSubmit || loading) return
    setSubmitted(true)
    const result = await onSubmit(title.trim(), content.trim(), selectedFile ?? undefined)
    if (!result) setSubmitted(false)
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
          <button type="button" className={mode === 'paste' ? 'is-active' : ''} onClick={() => setMode('paste')}><Icon name="doc" /> 텍스트 입력</button>
          <label className={`mode-tab ${mode === 'upload' ? 'is-active' : ''}`}><input type="file" accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf" onChange={(event) => { setMode('upload'); handleFile(event) }} /><Icon name="plus" /> 파일 업로드</label>
        </div>
        <label className="field-label">제목<span>선택</span><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="자료의 제목을 입력하세요" /></label>
        <label className="field-label">본문<span>필수</span><textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="메모, 업무자료, 읽은 내용 등의 텍스트를 붙여 넣으세요." rows={9} /></label>
        {selectedFile && <div className="file-note"><Icon name="check" /> {selectedFile.name} 파일이 선택되었습니다.</div>}
        <div className="ai-notice"><span className="notice-icon"><Icon name="spark" /></span><p>분석을 시작하면 원문을 저장하고 AI 분석 및 개념·관계를 생성한 뒤 지식 그래프에 반영합니다.</p></div>
        <div className="modal-actions"><Button type="button" variant="ghost" onClick={onClose}>취소</Button><Button type="submit" variant="primary" disabled={!canSubmit}>분석 시작 <Icon name="arrow" /></Button></div>
      </form>}
      {submitted && <div className="analysis-progress">
        <div className="analysis-orbit"><span className="orbit-core"><Icon name="spark" /></span><span className="orbit-ring ring-one" /><span className="orbit-ring ring-two" /></div>
        <Badge tone="teal">{loading ? 'ANALYSIS RUNNING' : 'ANALYSIS COMPLETE'}</Badge>
        <h3>{loading ? '자료를 분석하고 연결하는 중입니다' : '분석이 완료되었습니다'}</h3>
        <p>{loading ? '백엔드가 원문을 청킹하고 개념과 관계를 생성하고 있습니다.' : '자료가 그래프와 검색 인덱스에 반영되었습니다.'}</p>
        <div className="analysis-steps">{analysisSteps.map((item, index) => <div className={!loading ? 'is-done' : index === 0 ? 'is-current' : ''} key={item}><span>{!loading ? <Icon name="check" /> : index + 1}</span><label>{item}</label></div>)}</div>
        {!loading && <Button variant="primary" onClick={onClose}>그래프에서 보기 <Icon name="arrow" /></Button>}
      </div>}
    </section>
  </div>
}
