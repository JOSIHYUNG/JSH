import { useState } from 'react'
import { AppProviders } from './AppProviders'
import { AppShell } from '../features/shell/AppShell'
import { TopBar } from '../features/shell/TopBar'
import { QuestionBar } from '../features/shell/QuestionBar'
import { KnowledgeGraph } from '../features/graph/KnowledgeGraph'
import { RecentDocuments } from '../features/documents/RecentDocuments'
import { AddDocumentModal } from '../features/documents/AddDocumentModal'
import { DocumentPanel } from '../features/documents/DocumentPanel'
import { ConceptPanel } from '../features/concepts/ConceptPanel'
import { QuestionResultPanel } from '../features/questions/QuestionResultPanel'
import { QuestionHistoryPanel } from '../features/questions/QuestionHistoryPanel'
import { LoadingState } from '../features/feedback/LoadingState'
import { useKnowledgeController } from '../hooks/useKnowledgeController'
import type { GraphNode, QuestionSource } from '../domain/knowledge'
import { Icon } from '../components/primitives/Icon'
import { Badge } from '../components/primitives/Badge'

function App() {
  const controller = useKnowledgeController()
  const [addModalOpen, setAddModalOpen] = useState(false)

  const selectNode = (node: GraphNode) => {
    if (node.entity_type === 'document') void controller.openDocument(node.entity_id)
    if (node.entity_type === 'concept') void controller.openConcept(node.entity_id)
  }

  const openSource = (source: QuestionSource) => {
    if (source.openable && source.document_id) void controller.openDocument(source.document_id)
  }

  const submitQuestion = (question: string) => { void controller.ask(question) }
  const closePanel = () => controller.setPanel(null)

  const submitDocument = async (title: string, content: string, file?: File) => {
    const document = await controller.addDocument(title, content, file)
    if (document) setAddModalOpen(false)
    return document
  }

  return <AppProviders>
    <AppShell>
      <TopBar status={controller.systemStatus} onAdd={() => setAddModalOpen(true)} onHistory={() => controller.setHistoryOpen(true)} />
      <section className="hero-copy"><div><span className="eyebrow">PERSONAL KNOWLEDGE UNIVERSE / 01</span><h1>흩어진 지식이 연결되는<br /><em>나만의 지식 우주</em></h1></div><div className="hero-note"><span className="hero-line" /><p>쌓여진 메모를 하나로 모으고<br />필요한 순간, 근거와 함께 다시 꺼내보세요.</p></div></section>
      <QuestionBar loading={controller.questionLoading} onSubmit={submitQuestion} />
      <section className="stat-strip"><div><span className="stat-number">{controller.documents.length}</span><span className="stat-label">자료</span></div><div><span className="stat-number">{controller.graph?.node_count ?? '—'}</span><span className="stat-label">노드</span></div><div><span className="stat-number">{controller.graph?.edge_count ?? '—'}</span><span className="stat-label">연결</span></div><div className="stat-spacer" />{controller.notice && <p className="inline-notice"><Icon name="alert" /> {controller.notice}</p>}</section>
      <KnowledgeGraph snapshot={controller.graph} loading={controller.initialLoading} onNodeSelect={selectNode} onFiltersChange={controller.updateFilters} onResetFilters={() => controller.updateFilters({ conceptType: 'all', includeChunks: false, recentDays: null, minStrength: .2 })} />
      <section className="below-grid"><RecentDocuments documents={controller.documents} onOpen={controller.openDocument} /><section className="signal-card"><div className="signal-heading"><span className="eyebrow">SYSTEM SIGNAL</span><Badge tone="teal">OPENAI API / LOCAL DATA</Badge></div><h2>질문하기 전에,<br /><em>구조를 둘러보세요</em></h2><p>그래프의 노드를 선택하면 개념과 문서를 탐색하고, 질문하면 저장된 지식에서 근거를 찾아 답변을 확인할 수 있습니다.</p><div className="signal-footer"><span><Icon name="orbit" /> local knowledge space</span><span>v0.2 api</span></div></section></section>
      <footer className="app-footer"><span>JSH / SECOND BRAIN</span><span>Built for one curious mind</span></footer>
      {controller.panel && controller.panel.kind === 'loading' && <div className="side-panel-layer"><div className="panel-scrim" onClick={closePanel} /><aside className="context-panel loading-panel"><LoadingState label={controller.panel.label} /></aside></div>}
      {controller.panel?.kind === 'document' && <div className="side-panel-layer"><div className="panel-scrim" onClick={closePanel} /><DocumentPanel document={controller.panel.data} onClose={closePanel} onOpenConcept={controller.openConcept} onAskConcept={submitQuestion} /></div>}
      {controller.panel?.kind === 'concept' && <div className="side-panel-layer"><div className="panel-scrim" onClick={closePanel} /><ConceptPanel concept={controller.panel.data} onClose={closePanel} onOpenDocument={controller.openDocument} onOpenConcept={controller.openConcept} onAsk={submitQuestion} /></div>}
      {controller.panel?.kind === 'question' && <div className="side-panel-layer"><div className="panel-scrim" onClick={closePanel} /><QuestionResultPanel result={controller.panel.data} onClose={closePanel} onOpenSource={openSource} onAskConcept={submitQuestion} /></div>}
      {controller.historyOpen && <div className="side-panel-layer"><div className="panel-scrim" onClick={() => controller.setHistoryOpen(false)} /><QuestionHistoryPanel history={controller.history} onClose={() => controller.setHistoryOpen(false)} onOpen={controller.openHistoryQuestion} /></div>}
      <AddDocumentModal open={addModalOpen} loading={controller.addLoading} onClose={() => setAddModalOpen(false)} onSubmit={submitDocument} />
    </AppShell>
  </AppProviders>
}

export default App
