export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export const appConfig = {
  graphNodeLimit: 500,
  graphEdgeLimit: 1500,
  analysisEventReconnectMs: 1800,
}
