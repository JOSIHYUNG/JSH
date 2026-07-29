export type PaginationMeta = {
  page: number
  page_size: number
  total_items: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

export type ApiEnvelope<T> = {
  data: T
  meta: {
    request_id: string
    generated_at: string
    pagination?: PaginationMeta
    warnings?: string[]
  }
  error: null
}

export type ApiErrorPayload = {
  code: string
  message: string
  details?: Record<string, unknown>
  retryable: boolean
}

export type ApiErrorEnvelope = {
  data: null
  meta: { request_id: string; generated_at: string }
  error: ApiErrorPayload
}
