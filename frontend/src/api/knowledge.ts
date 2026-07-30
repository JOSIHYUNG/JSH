import type { AnalysisJob, ConceptDetail, ConversationDetail, ConversationSummary, DocumentDetail, DocumentSummary, GraphFilters, GraphSnapshot, QuestionHistorySummary, QuestionResult, SystemStatus } from '../domain/knowledge'
import { API_BASE_URL } from '../config'
import { ApiError, apiRequest } from './client'

type ApiDocumentDetail = {
  document: DocumentSummary
  chunks: DocumentDetail['chunks']
  concepts: DocumentDetail['concepts']
  latest_job: DocumentDetail['latest_job']
}

export const knowledgeApi = {
  async listDocuments(params = ''): Promise<DocumentSummary[]> {
    const result = await apiRequest<{ items: DocumentSummary[] }>(`/documents${params}`)
    return result.items
  },

  async createDocument(title: string, content: string): Promise<DocumentSummary> {
    const result = await apiRequest<{ document: DocumentSummary }>('/documents', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, content, auto_analyze: true }) })
    return result.document
  },

  async uploadDocument(file: File, title?: string): Promise<DocumentSummary> {
    const body = new FormData()
    body.append('file', file)
    if (title) body.append('title', title)
    body.append('auto_analyze', 'true')
    const result = await apiRequest<{ document: DocumentSummary }>('/documents/upload', { method: 'POST', body })
    return result.document
  },

  async getDocument(id: number, range?: { startChar: number; endChar: number }): Promise<DocumentDetail> {
    const result = await apiRequest<ApiDocumentDetail>(`/documents/${id}`)
    const params = new URLSearchParams()
    if (range) { params.set('start_char', String(range.startChar)); params.set('end_char', String(range.endChar)) }
    const original = await apiRequest<{ content: string; start_char: number; end_char: number; highlight_start_char: number | null; highlight_end_char: number | null }>(`/documents/${id}/original${params.size ? `?${params.toString()}` : ''}`)
    return { ...result.document, chunks: result.chunks, concepts: result.concepts, original_content: original.content, original_range: range ? { start_char: original.start_char, end_char: original.end_char, highlight_start_char: original.highlight_start_char, highlight_end_char: original.highlight_end_char } : undefined, latest_job: result.latest_job }
  },

  async getDocumentStatus(id: number): Promise<DocumentSummary & { latest_job: AnalysisJob | null }> {
    const result = await apiRequest<ApiDocumentDetail>(`/documents/${id}?include_chunks=false&include_concepts=false`)
    return { ...result.document, latest_job: result.latest_job }
  },

  getConcept: (id: number): Promise<ConceptDetail> => apiRequest(`/concepts/${id}`),

  deleteDocument: (id: number): Promise<void> => apiRequest(`/documents/${id}`, { method: 'DELETE' }),

  async updateDocument(id: number, payload: { title?: string; content?: string; auto_analyze?: boolean }): Promise<{ document: DocumentSummary; job: DocumentDetail['latest_job'] }> {
    return apiRequest(`/documents/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
  },

  async reanalyzeDocument(id: number): Promise<DocumentSummary> {
    const result = await apiRequest<{ document: DocumentSummary }>(`/documents/${id}/reanalyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
    return result.document
  },

  cancelAnalysis: (id: number): Promise<void> => apiRequest(`/documents/${id}/analysis/cancel`, { method: 'POST' }),

  watchAnalysis(
    id: number,
    handlers: {
      onProgress: (job: Pick<AnalysisJob, 'stage' | 'progress' | 'message'>) => void
      onCompleted: () => void
      onFailed: (message: string) => void
      onConnectionError: () => void
    },
  ): () => void {
    const stream = new EventSource(`${API_BASE_URL}/documents/${id}/analysis/events`)
    const read = (event: MessageEvent<string>) => {
      try {
        return JSON.parse(event.data) as { stage?: string; progress?: number; message?: string; error?: { message?: string } }
      } catch {
        return {}
      }
    }
    const progress = (event: Event) => {
      const data = read(event as MessageEvent<string>)
      handlers.onProgress({
        stage: data.stage ?? 'processing',
        progress: data.progress ?? 0,
        message: data.message ?? '자료를 분석하고 있습니다.',
      })
    }
    stream.addEventListener('analysis.started', progress)
    stream.addEventListener('analysis.progress', progress)
    stream.addEventListener('analysis.completed', () => {
      stream.close()
      handlers.onCompleted()
    })
    stream.addEventListener('analysis.failed', (event) => {
      const data = read(event as MessageEvent<string>)
      stream.close()
      handlers.onFailed(data.error?.message ?? data.message ?? '자료 분석에 실패했습니다.')
    })
    stream.addEventListener('analysis.canceled', () => {
      stream.close()
      handlers.onFailed('자료 분석을 취소했습니다. 원문은 보존되었습니다.')
    })
    stream.onerror = () => {
      stream.close()
      handlers.onConnectionError()
    }
    return () => stream.close()
  },

  async getGraph(filters: GraphFilters): Promise<GraphSnapshot> {
    const params = new URLSearchParams({ include_chunks: String(filters.includeChunks), min_strength: String(filters.minStrength), node_types: filters.includeChunks ? 'document,chunk,concept' : 'document,concept' })
    if (filters.conceptType !== 'all') params.set('concept_types', filters.conceptType)
    if (filters.recentDays) params.set('recent_days', String(filters.recentDays))
    const result = await apiRequest<GraphSnapshot>(`/graph?${params.toString()}`)
    return { ...result, filters }
  },

  ask: (question: string, conversationId?: number | null): Promise<QuestionResult> => apiRequest('/questions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, ...(conversationId ? { conversation_id: conversationId } : {}) }) }),

  async listConversations(): Promise<ConversationSummary[]> {
    try {
      const result = await apiRequest<{ items: ConversationSummary[] }>('/conversations?page=1&page_size=50')
      return result.items
    } catch (error) {
      // Keep the existing single-question screen usable while an old backend
      // process is being restarted. The new chat API becomes available after
      // the backend migration/restart completes.
      if (error instanceof ApiError && error.status === 404) return []
      throw error
    }
  },

  createConversation: (title?: string): Promise<ConversationSummary> => apiRequest('/conversations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(title ? { title } : {}) }),

  getConversation: (id: number): Promise<ConversationDetail> => apiRequest(`/conversations/${id}`),

  renameConversation: (id: number, title: string): Promise<ConversationSummary> => apiRequest(`/conversations/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }) }),

  deleteConversation: (id: number): Promise<void> => apiRequest(`/conversations/${id}`, { method: 'DELETE' }),

  askInConversation: (id: number, question: string): Promise<QuestionResult> => apiRequest(`/conversations/${id}/questions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) }),

  async listQuestionHistory(): Promise<QuestionHistorySummary[]> {
    const result = await apiRequest<{ items: QuestionHistorySummary[] }>('/questions?page=1&page_size=20')
    return result.items
  },

  getQuestion: (id: number): Promise<QuestionResult> => apiRequest(`/questions/${id}`),
  rerunQuestion: (id: number, question?: string): Promise<QuestionResult> => apiRequest(`/questions/${id}/rerun`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(question ? { question } : {}) }),
  deleteQuestion: (id: number): Promise<void> => apiRequest(`/questions/${id}`, { method: 'DELETE' }),
  getSystemStatus: (): Promise<SystemStatus> => apiRequest('/system/status'),
}
