import { API_BASE_URL } from '../config'
import type { ApiEnvelope, ApiErrorEnvelope } from '../domain/api'

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly retryable: boolean
  readonly requestId: string | null

  constructor(payload: { code: string; message: string; retryable: boolean }, status: number, requestId: string | null) {
    super(payload.message)
    this.name = 'ApiError'
    this.code = payload.code
    this.status = status
    this.retryable = payload.retryable
    this.requestId = requestId
  }
}

async function readEnvelope<T>(response: Response): Promise<ApiEnvelope<T> | ApiErrorEnvelope> {
  try {
    return await response.json() as ApiEnvelope<T> | ApiErrorEnvelope
  } catch {
    throw new ApiError({ code: 'INVALID_API_RESPONSE', message: '서버 응답을 읽을 수 없습니다.', retryable: true }, response.status, response.headers.get('X-Request-ID'))
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { Accept: 'application/json', ...init.headers },
  })
  const envelope = await readEnvelope<T>(response)
  if (!response.ok || envelope.error) {
    const error = envelope.error ?? { code: 'HTTP_ERROR', message: `요청에 실패했습니다. (${response.status})`, retryable: response.status >= 500 }
    throw new ApiError(error, response.status, envelope.meta.request_id)
  }
  return envelope.data
}
