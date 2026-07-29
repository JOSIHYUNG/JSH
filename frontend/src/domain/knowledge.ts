export type ConceptType =
  | 'organization'
  | 'organization_unit'
  | 'person'
  | 'country'
  | 'region'
  | 'place'
  | 'technology'
  | 'equipment'
  | 'system'
  | 'project_program'
  | 'policy_law'
  | 'event'
  | 'document'

export type DocumentStatus = 'draft' | 'processing' | 'ready' | 'failed' | 'deleting'
export type EntityType = 'document' | 'chunk' | 'concept'

export type DocumentSummary = {
  id: number
  title: string
  filename: string | null
  source_type: 'paste' | 'upload'
  media_type: string
  summary: string
  keywords: string[]
  status: DocumentStatus
  character_count: number
  chunk_count: number
  concept_count: number
  created_at: string
  updated_at: string
}

export type DocumentChunk = {
  id: number
  document_id: number
  chunk_index: number
  content: string
  preview: string
  start_char: number
  end_char: number
  concept_ids: number[]
}

export type ConceptSummary = {
  id: number
  concept_type: ConceptType
  canonical_name: string
  english_name: string | null
  abbreviation: string | null
  description: string
  document_count: number
  chunk_count: number
  visibility: 'visible' | 'hidden' | 'orphaned'
}

export type ConceptAlias = {
  alias: string
  alias_type: 'ko' | 'en' | 'abbreviation' | 'source_mention'
  source_chunk_id: number | null
  confidence: number
}

export type ConceptRelation = {
  concept: ConceptSummary
  relation_type: string
  strength: number
  evidence_chunk_id: number | null
  explanation: string
}

export type ConceptDetail = ConceptSummary & {
  aliases: ConceptAlias[]
  source_chunks: DocumentChunk[]
  related_concepts: ConceptRelation[]
}

export type DocumentDetail = DocumentSummary & {
  chunks: DocumentChunk[]
  concepts: ConceptSummary[]
  original_content: string
  latest_job: AnalysisJob | null
}

export type GraphNode = {
  id: string
  entity_type: EntityType
  entity_id: number
  label: string
  subtype: ConceptType | null
  size: number
  color_token: string
  metadata: {
    title?: string
    summary?: string
    connection_count?: number
    status?: DocumentStatus
  }
}

export type GraphEdge = {
  id: string
  source: string
  target: string
  edge_type: 'contains' | 'mentions' | 'relates'
  relation_type: string | null
  strength: number
  is_directed: boolean
  evidence_chunk_id: number | null
}

export type GraphFilters = {
  conceptType: ConceptType | 'all'
  includeChunks: boolean
  recentDays: number | null
  minStrength: number
}

export type GraphSnapshot = {
  nodes: GraphNode[]
  edges: GraphEdge[]
  filters: GraphFilters
  truncated: boolean
  node_count: number
  edge_count: number
}

export type QuestionSource = {
  rank: number
  citation_key: string
  document_id: number | null
  chunk_id: number | null
  document_title: string
  document_status: 'ready' | 'deleted' | 'reanalyzed'
  chunk_preview: string
  start_char: number | null
  end_char: number | null
  score: number
  mapping_confidence: number
  openable: boolean
}

export type QuestionStatus = 'queued' | 'retrieving' | 'generating' | 'completed' | 'no_evidence' | 'failed'

export type QuestionResult = {
  id: number
  question: string
  status: QuestionStatus
  answer_markdown: string | null
  answer_language: string | null
  sources: QuestionSource[]
  related_concepts: ConceptSummary[]
  retrieval: {
    provider: 'vector_store' | 'lexical_fallback' | 'none'
    candidate_count: number
    returned_count: number
    mapping_failures: number
    top_score: number | null
    used_chunk_ids: number[]
  }
  created_at: string
  completed_at: string | null
}

export type QuestionHistorySummary = {
  id: number
  question_preview: string
  status: QuestionStatus
  answer_preview: string | null
  evidence_count: number
  created_at: string
  completed_at: string | null
}

export type AnalysisJob = {
  id: number
  document_id: number
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancel_requested' | 'canceled'
  stage: string
  progress: number
  message: string
  retry_count: number
  error: { code: string; message: string } | null
  started_at: string | null
  completed_at: string | null
}

export type AnalysisPreview = {
  kind: 'title' | 'summary' | 'keyword' | 'concept' | 'relation'
  payload: Record<string, string | number | null>
}

export type SystemStatus = {
  database: 'ready' | 'degraded'
  file_storage: 'ready' | 'degraded'
  openai_configured: boolean
  vector_store_configured: boolean
  analysis_running: number
  app_version: string
}

export const conceptTypeLabels: Record<ConceptType, string> = {
  organization: '조직',
  organization_unit: '조직 단위',
  person: '인물',
  country: '국가',
  region: '지역',
  place: '장소',
  technology: '기술',
  equipment: '장비',
  system: '체계',
  project_program: '사업·프로그램',
  policy_law: '정책·법률',
  event: '사건',
  document: '문서',
}

export const conceptTypeOrder = Object.keys(conceptTypeLabels) as ConceptType[]
