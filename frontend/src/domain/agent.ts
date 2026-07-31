import type { QuestionResult } from './knowledge'

export type AgentRunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'canceled' | 'max_turns'

export type AgentRunSummary = {
  id: number
  question_id: number
  conversation_id: number
  turn_index: number | null
  status: AgentRunStatus
  stage: string
  current_turn: number
  max_turns: number
  tool_call_count: number
  stop_reason: string | null
  error: { code: string; message: string; retryable?: boolean } | null
  created_at: string
  completed_at: string | null
}

export type AgentActivityEvent = {
  sequence: number
  run_id: number
  turn: number
  type: string
  tool: string | null
  label: string | null
  status: 'started' | 'completed' | 'failed' | 'terminal' | null
  query_preview: string | null
  node_labels: string[]
  result_count: number | null
  error_code: string | null
  created_at: string
}

export type AgentWebSource = {
  citation_key: string
  url: string
  title: string | null
  publisher: string | null
  rank: number
}

export type AgentRunPayload = {
  run: AgentRunSummary
  result: QuestionResult | null
  web_sources: AgentWebSource[]
}
