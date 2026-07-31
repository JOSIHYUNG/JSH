import { API_BASE_URL } from '../config'
import type { AgentActivityEvent, AgentRunPayload, AgentRunSummary } from '../domain/agent'
import { apiRequest } from './client'

type AgentEventHandlers = {
  onActivity: (event: AgentActivityEvent) => void
  onError?: () => void
  onTerminal?: (event: AgentActivityEvent) => void
}

const terminalTypes = new Set(['run_completed', 'run_failed', 'run_canceled', 'run_max_turns'])

export const agentApi = {
  createRun(question: string, conversationId?: number | null): Promise<AgentRunSummary> {
    return apiRequest<AgentRunSummary>('/agent/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, ...(conversationId ? { conversation_id: conversationId } : {}) }),
    })
  },

  getRun(id: number): Promise<AgentRunPayload> {
    return apiRequest<AgentRunPayload>(`/agent/runs/${id}`)
  },

  cancelRun(id: number): Promise<AgentRunSummary> {
    return apiRequest<AgentRunSummary>(`/agent/runs/${id}/cancel`, { method: 'POST' })
  },

  streamRunEvents(id: number, handlers: AgentEventHandlers, after = 0): () => void {
    const stream = new EventSource(`${API_BASE_URL}/agent/runs/${id}/events?after=${after}`)
    stream.addEventListener('activity', (event) => {
      try {
        const activity = JSON.parse((event as MessageEvent<string>).data) as AgentActivityEvent
        handlers.onActivity(activity)
        if (terminalTypes.has(activity.type)) handlers.onTerminal?.(activity)
      } catch {
        // A malformed event should not tear down the polling fallback.
      }
    })
    stream.onerror = () => handlers.onError?.()
    return () => stream.close()
  },
}
