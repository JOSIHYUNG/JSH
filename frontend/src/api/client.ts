import { API_BASE_URL } from '../config'
import type { ApiEnvelope, ApiErrorEnvelope } from '../domain/api'

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly retryable: boolean
  readonly requestId: string | null
  readonly details: Record<string, unknown>

  constructor(payload: { code: string; message: string; retryable: boolean; details?: Record<string, unknown> }, status: number, requestId: string | null) {
    super(payload.message)
    this.name = 'ApiError'
    this.code = payload.code
    this.status = status
    this.retryable = payload.retryable
    this.requestId = requestId
    this.details = payload.details ?? {}
  }
}

async function readEnvelope<T>(response: Response): Promise<ApiEnvelope<T> | ApiErrorEnvelope> {
  try {
    return await response.json() as ApiEnvelope<T> | ApiErrorEnvelope
  } catch {
    throw new ApiError({ code: 'INVALID_API_RESPONSE', message: '서버 응답을 읽을 수 없습니다.', retryable: true }, response.status, response.headers.get('X-Request-ID'))
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}, timeoutMs = 100_000): Promise<T> {
  const controller = new AbortController()
  const externalSignal = init.signal
  const abortFromExternal = () => controller.abort(externalSignal?.reason)
  if (externalSignal?.aborted) abortFromExternal()
  else externalSignal?.addEventListener('abort', abortFromExternal, { once: true })
  const timeout = globalThis.setTimeout(() => controller.abort('timeout'), timeoutMs)
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { Accept: 'application/json', ...init.headers },
    })
    if (response.status === 204) return undefined as T
    const envelope = await readEnvelope<T>(response)
    if (!response.ok || envelope.error) {
      const error = envelope.error ?? { code: 'HTTP_ERROR', message: `요청에 실패했습니다. (${response.status})`, retryable: response.status >= 500 }
      throw new ApiError(error, response.status, envelope.meta.request_id)
    }
    return envelope.data
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (controller.signal.aborted) {
      throw new ApiError({ code: 'REQUEST_TIMEOUT', message: '요청 시간이 초과되었습니다. 다시 시도해 주세요.', retryable: true }, 0, null)
    }
    throw new ApiError({ code: 'NETWORK_ERROR', message: '백엔드 서버에 연결하지 못했습니다.', retryable: true }, 0, null)
  } finally {
    globalThis.clearTimeout(timeout)
    externalSignal?.removeEventListener('abort', abortFromExternal)
  }
}
