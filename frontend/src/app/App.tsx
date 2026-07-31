import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { AppProviders } from './AppProviders'
import { AppShell } from '../features/shell/AppShell'
import { TopBar } from '../features/shell/TopBar'
import { QuestionBar } from '../features/shell/QuestionBar'
import { RecentDocuments } from '../features/documents/RecentDocuments'
import { AddDocumentModal } from '../features/documents/AddDocumentModal'
import { DocumentPanel } from '../features/documents/DocumentPanel'
import { ConceptPanel } from '../features/concepts/ConceptPanel'
import { ChatPanel } from '../features/questions/ChatPanel'
import { QuestionHistoryPanel } from '../features/questions/QuestionHistoryPanel'
import { LoadingState } from '../features/feedback/LoadingState'
import { useKnowledgeController } from '../hooks/useKnowledgeController'
import { useAgentRunEvents } from '../hooks/useAgentRunEvents'
import type { GraphNode, QuestionSource } from '../domain/knowledge'
import { Icon } from '../components/primitives/Icon'
import { Badge } from '../components/primitives/Badge'

const KnowledgeGraph = lazy(() => import('../features/graph/KnowledgeGraph').then((module) => ({ default: module.KnowledgeGraph })))

function App() {
  const controller = useKnowledgeController()
  const agentActivity = useAgentRunEvents(controller.agentRun?.id ?? null)
  const { historyOpen, panel, setHistoryOpen, setPanel } = controller
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [questionDraft, setQuestionDraft] = useState('')
  const [focusEntity, setFocusEntity] = useState<{ entity_type: GraphNode['entity_type']; entity_id: number } | null>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const overlayOpen = addModalOpen || historyOpen || panel !== null || (controller.questionLoading && !!controller.agentRun)
  const questionPanelResult = panel?.kind === 'question' ? panel.data : null

  useEffect(() => {
    // The main screen does not restore panels from URL state. Remove legacy
    // conversation query strings so refreshing the app always keeps a clean
    // root URL while conversation state remains in the application store.
    if (window.location.pathname === '/' && window.location.search) {
      window.history.replaceState(window.history.state, document.title, `${window.location.pathname}${window.location.hash}`)
    }
  }, [])

  useEffect(() => {
    if (!overlayOpen) return
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusDialog = () => {
      const dialog = document.querySelector<HTMLElement>('.modal-layer [role="dialog"], .side-panel-layer [role="dialog"], .side-panel-layer .context-panel')
      const first = dialog?.querySelector<HTMLElement>('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])')
      if (first) first.focus()
      else dialog?.focus()
    }
    const frame = window.requestAnimationFrame(focusDialog)
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return
      const dialog = document.querySelector<HTMLElement>('.modal-layer [role="dialog"], .side-panel-layer [role="dialog"], .side-panel-layer .context-panel')
      if (!dialog) return
      const focusable = [...dialog.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')]
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', trapFocus)
    return () => {
      window.cancelAnimationFrame(frame)
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', trapFocus)
      previousFocusRef.current?.focus()
      previousFocusRef.current = null
    }
  }, [overlayOpen])

  useEffect(() => {
    if (!overlayOpen) return
    const closeTopOverlay = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (addModalOpen) setAddModalOpen(false)
      else if (historyOpen) setHistoryOpen(false)
      else setPanel(null)
    }
    window.addEventListener('keydown', closeTopOverlay)
    return () => window.removeEventListener('keydown', closeTopOverlay)
  }, [addModalOpen, historyOpen, overlayOpen, setHistoryOpen, setPanel])

  const selectNode = (node: GraphNode) => {
    setFocusEntity({ entity_type: node.entity_type, entity_id: node.entity_id })
    if (node.entity_type === 'document') void controller.openDocument(node.entity_id)
    if (node.entity_type === 'concept') void controller.openConcept(node.entity_id)
    if (node.entity_type === 'chunk' && node.metadata.document_id) void controller.openDocument(node.metadata.document_id, node.metadata.start_char !== undefined && node.metadata.end_char !== undefined ? { startChar: node.metadata.start_char, endChar: node.metadata.end_char } : undefined)
  }

  const openSource = (source: QuestionSource) => {
    if (source.openable && source.document_id) void controller.openDocument(source.document_id, source.start_char !== null && source.end_char !== null ? { startChar: source.start_char, endChar: source.end_char } : undefined)
  }

  const submitQuestion = (question: string) => { setQuestionDraft(''); void controller.ask(question) }
  const closePanel = () => controller.setPanel(null)
  const backToHistory = () => {
    controller.setPanel(null)
    void controller.openHistory()
  }
  const editQuestion = (question: string) => {
    setQuestionDraft(question)
    closePanel()
    window.requestAnimationFrame(() => {
      const input = document.querySelector<HTMLInputElement>('.question-input-wrap input')
      input?.focus()
      input?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }

  const submitDocument = async (title: string, content: string, file?: File) => {
    return controller.addDocument(title, content, file)
  }

  const viewAddedDocument = (id: number) => {
    setAddModalOpen(false)
    setFocusEntity({ entity_type: 'document', entity_id: id })
    void controller.openDocument(id)
  }

  return <AppProviders>
    <AppShell>
      <TopBar status={controller.systemStatus} onAdd={() => setAddModalOpen(true)} onHistory={() => void controller.openHistory()} />
      <section className="hero-copy"><div><span className="eyebrow">PERSONAL KNOWLEDGE UNIVERSE / 01</span><h1>흩어진 지식을 연결하는 <br></br><em>나만의 지식 우주 저장소</em></h1></div><div className="hero-note"><span className="hero-line" /><p>쌓여진 메모를 하나로 모으고<br />필요한 순간, 근거와 함께 다시 꺼내보세요.</p></div></section>
      <QuestionBar loading={controller.questionLoading} value={questionDraft} onValueChange={setQuestionDraft} onSubmit={submitQuestion} activeConversation={controller.activeConversation?.conversation ?? null} onNewConversation={() => { controller.startNewConversation(); setQuestionDraft('') }} />
      <section className="stat-strip"><div><span className="stat-number">{controller.documents.length}</span><span className="stat-label">자료</span></div><div><span className="stat-number">{controller.graph?.node_count ?? '—'}</span><span className="stat-label">노드</span></div><div><span className="stat-number">{controller.graph?.edge_count ?? '—'}</span><span className="stat-label">연결</span></div><div className="stat-spacer" />{controller.addLoading && <p className="inline-progress" role="status"><span className="loading-orbit" /> 자료 분석 {controller.addProgress?.progress ?? 0}%</p>}{controller.notice && <p className="inline-notice" role="alert"><Icon name="alert" /> {controller.notice}</p>}</section>
      <Suspense fallback={<section className="graph-section graph-loading"><LoadingState label="3D 그래프를 준비하는 중" /></section>}><KnowledgeGraph snapshot={controller.graph} loading={controller.initialLoading} focusEntity={focusEntity} onNodeSelect={selectNode} onFiltersChange={controller.updateFilters} onResetFilters={() => controller.updateFilters({ conceptType: 'all', includeChunks: false, recentDays: null, minStrength: .2 })} /></Suspense>
      <section className="below-grid"><RecentDocuments documents={controller.documents} onOpen={controller.openDocument} /><section className="signal-card"><div className="signal-heading"><span className="eyebrow">SYSTEM SIGNAL</span><Badge tone="teal">OPENAI API / LOCAL DATA</Badge></div><h2>질문하기 전에,<br /><em>구조를 둘러보세요</em></h2><p>그래프의 노드를 선택하면 개념과 문서를 탐색하고, 질문하면 저장된 지식에서 근거를 찾아 답변을 확인할 수 있습니다.</p><div className="signal-footer"><span><Icon name="orbit" /> local knowledge space</span><span>v0.2 api</span></div></section></section>
      <footer className="app-footer"><span>JSH / SECOND BRAIN</span><span>Built for one curious mind</span></footer>
      {controller.panel && controller.panel.kind === 'loading' && <div className="side-panel-layer"><div className="panel-scrim" onClick={closePanel} /><aside className="context-panel loading-panel" role="dialog" aria-modal="true" aria-label={controller.panel.label} tabIndex={-1}><LoadingState label={controller.panel.label} /></aside></div>}
      {controller.panel?.kind === 'document' && <div className="side-panel-layer"><div className="panel-scrim" onClick={closePanel} /><DocumentPanel document={controller.panel.data} onClose={closePanel} onOpenConcept={controller.openConcept} onAskConcept={submitQuestion} onDelete={controller.deleteDocument} onReanalyze={controller.reanalyzeDocument} onUpdate={controller.updateDocument} onOpenFullDocument={(id) => void controller.openDocument(id)} /></div>}
      {controller.panel?.kind === 'concept' && <div className="side-panel-layer"><div className="panel-scrim" onClick={closePanel} /><ConceptPanel concept={controller.panel.data} onClose={closePanel} onOpenDocument={controller.openDocument} onOpenConcept={controller.openConcept} onAsk={submitQuestion} onCenter={() => setFocusEntity({ entity_type: 'concept', entity_id: controller.panel?.kind === 'concept' ? controller.panel.data.id : 0 })} /></div>}
      {(controller.panel?.kind === 'question' || (controller.questionLoading && controller.agentRun)) && <div className="side-panel-layer"><div className="panel-scrim" onClick={closePanel} /><ChatPanel conversation={controller.activeConversation} latestResult={questionPanelResult} onBackToHistory={backToHistory} onOpenSource={openSource} onOpenGeneratedDocument={(id) => void controller.openDocument(id)} onAskConcept={submitQuestion} onAsk={submitQuestion} loading={controller.questionLoading} onRetry={(id) => void controller.rerunTurn(id)} onEdit={editQuestion} onNewConversation={() => { controller.startNewConversation(); setQuestionDraft('') }} onRename={(id, title) => void controller.renameConversation(id, title)} onDelete={(id) => void controller.deleteConversation(id)} agentRun={agentActivity.run ?? controller.agentRun} agentActivities={agentActivity.events} onCancelAgent={() => void controller.cancelAgentRun()} agentWebSources={controller.agentWebSources} agentQuestion={controller.agentQuestion} /></div>}
      {controller.historyOpen && <div className="side-panel-layer"><div className="panel-scrim" onClick={() => controller.setHistoryOpen(false)} /><QuestionHistoryPanel conversations={controller.conversations} onClose={() => controller.setHistoryOpen(false)} onOpen={(id) => void controller.openConversation(id)} onRename={(id, title) => void controller.renameConversation(id, title)} onDelete={(id) => void controller.deleteConversation(id)} /></div>}
      <AddDocumentModal open={addModalOpen} loading={controller.addLoading} progress={controller.addProgress} error={controller.addError} cancelAvailable={controller.addDocumentId !== null} onClose={() => setAddModalOpen(false)} onSubmit={submitDocument} onCancelAnalysis={() => void controller.cancelAddAnalysis()} onViewDocument={viewAddedDocument} />
    </AppShell>
  </AppProviders>
}

export default App
