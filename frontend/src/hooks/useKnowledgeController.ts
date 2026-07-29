import { useCallback, useEffect, useState } from 'react'
import type { ConceptDetail, DocumentDetail, DocumentSummary, GraphFilters, GraphSnapshot, QuestionHistorySummary, QuestionResult, SystemStatus } from '../domain/knowledge'
import { knowledgeApi } from '../api/knowledge'

export type PanelState =
  | { kind: 'document'; data: DocumentDetail }
  | { kind: 'concept'; data: ConceptDetail }
  | { kind: 'question'; data: QuestionResult }
  | { kind: 'loading'; label: string }
  | null

const initialFilters: GraphFilters = { conceptType: 'all', includeChunks: false, recentDays: null, minStrength: .2 }

const wait = (duration: number) => new Promise<void>((resolve) => window.setTimeout(resolve, duration))

async function waitForDocumentReady(id: number): Promise<DocumentSummary> {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const document = await knowledgeApi.getDocumentStatus(id)
    if (document.status === 'ready') return document
    if (document.status === 'failed') throw new Error('자료 분석에 실패했습니다.')
    await wait(500)
  }
  throw new Error('자료 분석 시간이 초과되었습니다.')
}

export function useKnowledgeController() {
  const [graph, setGraph] = useState<GraphSnapshot | null>(null)
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [history, setHistory] = useState<QuestionHistorySummary[]>([])
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [filters, setFilters] = useState<GraphFilters>(initialFilters)
  const [panel, setPanel] = useState<PanelState>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [questionLoading, setQuestionLoading] = useState(false)
  const [documentLoading, setDocumentLoading] = useState(false)
  const [addLoading, setAddLoading] = useState(false)

  const refresh = useCallback(async (nextFilters = filters) => {
    const [nextGraph, nextDocuments, nextHistory, nextSystem] = await Promise.all([
      knowledgeApi.getGraph(nextFilters),
      knowledgeApi.listDocuments(),
      knowledgeApi.listQuestionHistory(),
      knowledgeApi.getSystemStatus(),
    ])
    setGraph(nextGraph)
    setDocuments(nextDocuments)
    setHistory(nextHistory)
    setSystemStatus(nextSystem)
  }, [filters])

  useEffect(() => {
    void refresh().catch((error: unknown) => setNotice(error instanceof Error ? error.message : '지식 우주를 불러오지 못했습니다.')).finally(() => setInitialLoading(false))
  }, [refresh])

  const updateFilters = useCallback((nextFilters: GraphFilters) => {
    setFilters(nextFilters)
    void refresh(nextFilters).catch((error: unknown) => setNotice(error instanceof Error ? error.message : '그래프 필터를 적용하지 못했습니다.'))
  }, [refresh])

  const openDocument = useCallback(async (id: number) => {
    setPanel({ kind: 'loading', label: '문서를 여는 중' })
    setDocumentLoading(true)
    try {
      setPanel({ kind: 'document', data: await knowledgeApi.getDocument(id) })
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '문서를 열지 못했습니다.')
      setPanel(null)
    } finally {
      setDocumentLoading(false)
    }
  }, [])

  const openConcept = useCallback(async (id: number) => {
    setPanel({ kind: 'loading', label: '개념을 여는 중' })
    setDocumentLoading(true)
    try {
      setPanel({ kind: 'concept', data: await knowledgeApi.getConcept(id) })
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '개념을 열지 못했습니다.')
      setPanel(null)
    } finally {
      setDocumentLoading(false)
    }
  }, [])

  const ask = useCallback(async (question: string) => {
    setQuestionLoading(true)
    setNotice(null)
    try {
      const result = await knowledgeApi.ask(question)
      setPanel({ kind: 'question', data: result })
      setHistory(await knowledgeApi.listQuestionHistory())
      return result
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '질문을 처리하지 못했습니다.')
      return null
    } finally {
      setQuestionLoading(false)
    }
  }, [])

  const openHistoryQuestion = useCallback(async (id: number) => {
    setPanel({ kind: 'loading', label: '질문 기록을 복원하는 중' })
    try {
      setPanel({ kind: 'question', data: await knowledgeApi.getQuestion(id) })
      setHistoryOpen(false)
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '질문 기록을 열지 못했습니다.')
    }
  }, [])

  const addDocument = useCallback(async (title: string, content: string, file?: File) => {
    setAddLoading(true)
    setNotice(null)
    try {
      const created = file
        ? await knowledgeApi.uploadDocument(file, title)
        : await knowledgeApi.createDocument(title, content)
      const document = await waitForDocumentReady(created.id)
      await refresh()
      await openDocument(document.id)
      return document
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '자료를 추가하지 못했습니다.')
      return null
    } finally {
      setAddLoading(false)
    }
  }, [openDocument, refresh])

  return {
    graph,
    documents,
    history,
    systemStatus,
    filters,
    panel,
    historyOpen,
    notice,
    initialLoading,
    questionLoading,
    documentLoading,
    addLoading,
    setNotice,
    setHistoryOpen,
    setPanel,
    updateFilters,
    openDocument,
    openConcept,
    ask,
    openHistoryQuestion,
    addDocument,
    refresh,
  }
}
