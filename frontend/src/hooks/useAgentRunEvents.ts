import { useEffect, useState } from 'react'
import { agentApi } from '../api/agent'
import type { AgentActivityEvent, AgentRunSummary } from '../domain/agent'

const terminalTypes = new Set(['run_completed', 'run_failed', 'run_canceled', 'run_max_turns'])

export function useAgentRunEvents(runId: number | null) {
  const [events, setEvents] = useState<AgentActivityEvent[]>([])
  const [run, setRun] = useState<AgentRunSummary | null>(null)

  useEffect(() => {
    if (!runId) {
      setEvents([])
      setRun(null)
      return
    }
    setEvents([])
    setRun(null)
    const seen = new Set<number>()
    let polling = false
    const pollRun = async () => {
      if (polling) return
      polling = true
      try {
        const payload = await agentApi.getRun(runId)
        setRun(payload.run)
      } catch {
        // SSE remains the primary activity channel; the next poll retries.
      } finally {
        polling = false
      }
    }
    void pollRun()
    const pollTimer = window.setInterval(() => void pollRun(), 700)
    const close = agentApi.streamRunEvents(runId, {
      onActivity: (event) => {
        if (seen.has(event.sequence)) return
        seen.add(event.sequence)
        setEvents((current) => [...current, event].slice(-30))
      },
      onTerminal: () => close(),
      onError: () => {
        // The controller continues polling the canonical run endpoint.
      },
    })
    return () => {
      window.clearInterval(pollTimer)
      close()
    }
  }, [runId])

  const active = events.length > 0 && !terminalTypes.has(events[events.length - 1]?.type ?? '')
  return { events, active, run }
}
