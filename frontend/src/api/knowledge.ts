import type { ConceptDetail, DocumentDetail, DocumentSummary, GraphFilters, GraphSnapshot, QuestionHistorySummary, QuestionResult, SystemStatus } from '../domain/knowledge'
import { apiRequest } from './client'

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

  async getDocument(id: number): Promise<DocumentDetail> {
    const result = await apiRequest<ApiDocumentDetail>(`/documents/${id}`)
    const original = await apiRequest<{ content: string }>(`/documents/${id}/original`)
    return { ...result.document, chunks: result.chunks, concepts: result.concepts, original_content: original.content, latest_job: result.latest_job }
  },

  async getDocumentStatus(id: number): Promise<DocumentSummary> {
    const result = await apiRequest<ApiDocumentDetail>(`/documents/${id}?include_chunks=false&include_concepts=false`)
    return result.document
  },

  getConcept: (id: number): Promise<ConceptDetail> => apiRequest(`/concepts/${id}`),

  async getGraph(filters: GraphFilters): Promise<GraphSnapshot> {
    const params = new URLSearchParams({ include_chunks: String(filters.includeChunks), min_strength: String(filters.minStrength), node_types: filters.includeChunks ? 'document,chunk,concept' : 'document,concept' })
    if (filters.conceptType !== 'all') params.set('concept_types', filters.conceptType)
    const result = await apiRequest<GraphSnapshot>(`/graph?${params.toString()}`)
    return { ...result, filters }
  },

  ask: (question: string): Promise<QuestionResult> => apiRequest('/questions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) }),

  async listQuestionHistory(): Promise<QuestionHistorySummary[]> {
    const result = await apiRequest<{ items: QuestionHistorySummary[] }>('/questions?page=1&page_size=20')
    return result.items
  },

  getQuestion: (id: number): Promise<QuestionResult> => apiRequest(`/questions/${id}`),
  getSystemStatus: (): Promise<SystemStatus> => apiRequest('/system/status'),
}
