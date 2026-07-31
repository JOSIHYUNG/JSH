import { useCallback, useEffect, useState } from 'react'
import type { AnalysisJob, ConceptDetail, ConversationDetail, ConversationSummary, DocumentDetail, DocumentSummary, GraphFilters, GraphSnapshot, QuestionHistorySummary, QuestionResult, SystemStatus } from '../domain/knowledge'
import type { AgentRunPayload, AgentRunSummary, AgentWebSource } from '../domain/agent'
import { agentApi } from '../api/agent'
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
  for (let attempt = 0; attempt < 600; attempt += 1) {
    const document = await knowledgeApi.getDocumentStatus(id)
    if (document.status === 'ready') return document
    if (document.status === 'failed') throw new Error(document.latest_job?.error?.message || '자료 분석에 실패했습니다.')
    await wait(500)
  }
  throw new Error('자료 분석 시간이 초과되었습니다.')
}

async function waitForQuestion(id: number): Promise<QuestionResult> {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const result = await knowledgeApi.getQuestion(id)
    if (result.status === 'completed' || result.status === 'no_evidence' || result.status === 'failed') return result
    await wait(500)
  }
  throw new Error('질문 처리 시간이 초과되었습니다.')
}

async function waitForAgentRun(id: number): Promise<AgentRunPayload> {
  for (let attempt = 0; attempt < 600; attempt += 1) {
    const payload = await agentApi.getRun(id)
    if (['completed', 'no_evidence', 'failed', 'canceled', 'max_turns'].includes(payload.run.status) || payload.result?.status === 'no_evidence' || payload.result?.status === 'failed') return payload
    await wait(500)
  }
  throw new Error('Agent 실행 시간이 초과되었습니다.')
}

export type AnalysisProgress = Pick<AnalysisJob, 'stage' | 'progress' | 'message'>

async function pollDocumentReadyWithProgress(id: number, onProgress: (progress: AnalysisProgress) => void): Promise<DocumentSummary> {
  for (let attempt = 0; attempt < 600; attempt += 1) {
    const document = await knowledgeApi.getDocumentStatus(id)
    const job = document.latest_job
    if (job) onProgress({ stage: job.stage, progress: job.progress, message: job.message })
    if (document.status === 'ready') {
      onProgress({ stage: 'completed', progress: 100, message: '분석이 완료되었습니다.' })
      return document
    }
    if (document.status === 'failed') throw new Error(job?.error?.message || '자료 분석에 실패했습니다.')
    if (document.status === 'deleting') throw new Error('삭제 중인 자료입니다.')
    await wait(500)
  }
  throw new Error('자료 분석 시간이 초과되었습니다.')
}

async function waitForDocumentReadyWithProgress(id: number, onProgress: (progress: AnalysisProgress) => void): Promise<DocumentSummary> {
  return new Promise<DocumentSummary>((resolve, reject) => {
    let settled = false
    let fallbackStarted = false
    let closeStream = () => {}
    const timeout = window.setTimeout(() => {
      if (settled) return
      settled = true
      closeStream()
      reject(new Error('자료 분석 시간이 초과되었습니다.'))
    }, 305_000)
    const finish = (action: () => void) => {
      if (settled) return
      settled = true
      window.clearTimeout(timeout)
      closeStream()
      action()
    }
    const resolveCurrent = () => {
      void knowledgeApi.getDocumentStatus(id)
        .then((document) => finish(() => resolve(document)))
        .catch((error: unknown) => finish(() => reject(error)))
    }
    const fallback = () => {
      if (fallbackStarted || settled) return
      fallbackStarted = true
      closeStream()
      void pollDocumentReadyWithProgress(id, onProgress)
        .then((document) => finish(() => resolve(document)))
        .catch((error: unknown) => finish(() => reject(error)))
    }
    closeStream = knowledgeApi.watchAnalysis(id, {
      onProgress,
      onCompleted: resolveCurrent,
      onFailed: (message) => finish(() => reject(new Error(message))),
      onConnectionError: fallback,
    })
  })
}

export function useKnowledgeController() {
  const [graph, setGraph] = useState<GraphSnapshot | null>(null)
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [history, setHistory] = useState<QuestionHistorySummary[]>([])
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null)
  const [activeConversation, setActiveConversation] = useState<ConversationDetail | null>(null)
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [filters, setFilters] = useState<GraphFilters>(initialFilters)
  const [panel, setPanel] = useState<PanelState>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [questionLoading, setQuestionLoading] = useState(false)
  const [agentRun, setAgentRun] = useState<AgentRunSummary | null>(null)
  const [agentWebSources, setAgentWebSources] = useState<AgentWebSource[]>([])
  const [agentQuestion, setAgentQuestion] = useState<string | null>(null)
  const [conversationLoading, setConversationLoading] = useState(false)
  const [turnLoading, setTurnLoading] = useState(false)
  const [documentLoading, setDocumentLoading] = useState(false)
  const [addLoading, setAddLoading] = useState(false)
  const [addProgress, setAddProgress] = useState<AnalysisProgress | null>(null)
  const [addError, setAddError] = useState<string | null>(null)
  const [addDocumentId, setAddDocumentId] = useState<number | null>(null)

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
  }, [])

  const openDocument = useCallback(async (id: number, range?: { startChar: number; endChar: number }) => {
    setPanel({ kind: 'loading', label: '문서를 여는 중' })
    setDocumentLoading(true)
    try {
      setPanel({ kind: 'document', data: await knowledgeApi.getDocument(id, range) })
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '문서를 열지 못했습니다.')
      setPanel(null)
    } finally {
      setDocumentLoading(false)
    }
  }, [])

  const deleteDocument = useCallback(async (id: number) => {
    try {
      await knowledgeApi.deleteDocument(id)
      setPanel(null)
      await refresh()
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '자료를 삭제하지 못했습니다.')
    }
  }, [refresh])

  const updateDocument = useCallback(async (id: number, payload: { title?: string; content?: string }) => {
    setDocumentLoading(true)
    setNotice(null)
    try {
      const result = await knowledgeApi.updateDocument(id, { ...payload, auto_analyze: payload.content !== undefined })
      if (result.job) await waitForDocumentReady(id)
      await refresh()
      await openDocument(id)
      return true
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '자료를 수정하지 못했습니다.')
      return false
    } finally {
      setDocumentLoading(false)
    }
  }, [openDocument, refresh])

  const reanalyzeDocument = useCallback(async (id: number) => {
    setDocumentLoading(true)
    setNotice(null)
    try {
      await knowledgeApi.reanalyzeDocument(id)
      const document = await waitForDocumentReady(id)
      await refresh()
      await openDocument(document.id)
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '자료를 다시 분석하지 못했습니다.')
    } finally {
      setDocumentLoading(false)
    }
  }, [openDocument, refresh])

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
    setTurnLoading(true)
    setAgentQuestion(question)
    setNotice(null)
    try {
      const queued = await agentApi.createRun(question, activeConversationId)
      setAgentRun(queued)
      const conversationId = queued.conversation_id
      if (conversationId) setActiveConversationId(conversationId)
      const payload = await waitForAgentRun(queued.id)
      setAgentRun(payload.run)
      setAgentWebSources(payload.web_sources)
      const result = payload.result
      if (!result) throw new Error(payload.run.error?.message ?? 'Agent 응답을 받지 못했습니다.')
      setPanel({ kind: 'question', data: result })
      await refresh()
      const resolvedConversationId = result.conversation_id ?? conversationId
      if (resolvedConversationId) {
        setConversations(await knowledgeApi.listConversations())
        try {
          setActiveConversation(await knowledgeApi.getConversation(resolvedConversationId))
        } catch {
          // Keep the conversation id so the next turn can still target it
          // while the detail endpoint is temporarily unavailable.
          setActiveConversation(null)
        }
      }
      return result
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '질문을 처리하지 못했습니다.')
      return null
    } finally {
      setQuestionLoading(false)
      setTurnLoading(false)
    }
  }, [activeConversationId, refresh])

  const openConversation = useCallback(async (id: number) => {
    setConversationLoading(true)
    setNotice(null)
    try {
      const detail = await knowledgeApi.getConversation(id)
      setAgentRun(null)
      setAgentWebSources([])
      setAgentQuestion(null)
      setActiveConversationId(id)
      setActiveConversation(detail)
      const latest = detail.turns[detail.turns.length - 1]
      if (latest) setPanel({ kind: 'question', data: latest })
      setHistoryOpen(false)
      return detail
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '대화를 열지 못했습니다.')
      return null
    } finally {
      setConversationLoading(false)
    }
  }, [])

  const openHistory = useCallback(async () => {
    setHistoryOpen(true)
    try {
      setConversations(await knowledgeApi.listConversations())
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '대화 기록을 불러오지 못했습니다.')
    }
  }, [])

  const startNewConversation = useCallback(() => {
    setActiveConversationId(null)
    setActiveConversation(null)
    setPanel(null)
    setAgentRun(null)
    setAgentWebSources([])
    setAgentQuestion(null)
    setNotice(null)
  }, [])

  const renameConversation = useCallback(async (id: number, title: string) => {
    try {
      const summary = await knowledgeApi.renameConversation(id, title)
      setConversations((current) => current.map((item) => item.id === id ? summary : item))
      setActiveConversation((current) => current && current.conversation.id === id ? { ...current, conversation: summary } : current)
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '대화 제목을 수정하지 못했습니다.')
    }
  }, [])

  const deleteConversation = useCallback(async (id: number) => {
    try {
      await knowledgeApi.deleteConversation(id)
      setConversations((current) => current.filter((item) => item.id !== id))
      if (activeConversationId === id) startNewConversation()
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '대화를 삭제하지 못했습니다.')
    }
  }, [activeConversationId, startNewConversation])

  const rerunTurn = useCallback(async (id: number, question?: string) => {
    setQuestionLoading(true)
    setTurnLoading(true)
    try {
      const queued = await knowledgeApi.rerunQuestion(id, question)
      const result = await waitForQuestion(queued.id)
      const conversationId = result.conversation_id ?? queued.conversation_id
      if (conversationId) {
        setActiveConversationId(conversationId)
        try {
          setActiveConversation(await knowledgeApi.getConversation(conversationId))
        } catch {
          setActiveConversation(null)
        }
      }
      setPanel({ kind: 'question', data: result })
      await refresh()
      return result
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '질문을 다시 실행하지 못했습니다.')
      return null
    } finally {
      setQuestionLoading(false)
      setTurnLoading(false)
    }
  }, [refresh])

  const cancelAgentRun = useCallback(async () => {
    if (!agentRun || ['completed', 'failed', 'canceled', 'max_turns'].includes(agentRun.status)) return
    try {
      const canceled = await agentApi.cancelRun(agentRun.id)
      setAgentRun(canceled)
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : 'Agent 실행을 중단하지 못했습니다.')
    }
  }, [agentRun])

  const openHistoryQuestion = useCallback(async (id: number) => {
    setPanel({ kind: 'loading', label: '질문 기록을 복원하는 중' })
    try {
      setPanel({ kind: 'question', data: await knowledgeApi.getQuestion(id) })
      setHistoryOpen(false)
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '질문 기록을 열지 못했습니다.')
    }
  }, [])

  const rerunQuestion = useCallback(async (id: number) => {
    await rerunTurn(id)
  }, [rerunTurn])

  const deleteQuestion = useCallback(async (id: number) => {
    try {
      await knowledgeApi.deleteQuestion(id)
      if (panel?.kind === 'question' && panel.data.id === id) setPanel(null)
      setHistory(await knowledgeApi.listQuestionHistory())
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : '질문 기록을 삭제하지 못했습니다.')
    }
  }, [panel])

  const addDocument = useCallback(async (title: string, content: string, file?: File) => {
    setAddLoading(true)
    setAddProgress({ stage: 'received', progress: 0, message: '분석을 준비하고 있습니다.' })
    setAddError(null)
    setAddDocumentId(null)
    setNotice(null)
    try {
      const created = file
        ? await knowledgeApi.uploadDocument(file, title)
        : await knowledgeApi.createDocument(title, content)
      setAddDocumentId(created.id)
      const document = await waitForDocumentReadyWithProgress(created.id, setAddProgress)
      await refresh()
      return document
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '자료를 추가하지 못했습니다.'
      setAddError(message)
      setNotice(message)
      return null
    } finally {
      setAddLoading(false)
      setAddDocumentId(null)
    }
  }, [refresh])

  const cancelAddAnalysis = useCallback(async () => {
    if (!addDocumentId) return
    try {
      await knowledgeApi.cancelAnalysis(addDocumentId)
      setAddProgress((current) => ({
        stage: current?.stage ?? 'cancel_requested',
        progress: current?.progress ?? 0,
        message: '안전한 지점에서 분석을 취소하고 있습니다.',
      }))
    } catch (error: unknown) {
      setAddError(error instanceof Error ? error.message : '분석을 취소하지 못했습니다.')
    }
  }, [addDocumentId])

  return {
    graph,
    documents,
    history,
    conversations,
    activeConversationId,
    activeConversation,
    systemStatus,
    filters,
    panel,
    historyOpen,
    notice,
    initialLoading,
    questionLoading,
    agentRun,
    agentWebSources,
    agentQuestion,
    conversationLoading,
    turnLoading,
    documentLoading,
    addLoading,
    addProgress,
    addError,
    addDocumentId,
    setNotice,
    setHistoryOpen,
    openHistory,
    setPanel,
    updateFilters,
    openDocument,
    deleteDocument,
    updateDocument,
    reanalyzeDocument,
    openConcept,
    ask,
    openConversation,
    startNewConversation,
    renameConversation,
    deleteConversation,
    rerunTurn,
    cancelAgentRun,
    openHistoryQuestion,
    rerunQuestion,
    deleteQuestion,
    addDocument,
    cancelAddAnalysis,
    refresh,
  }
}
