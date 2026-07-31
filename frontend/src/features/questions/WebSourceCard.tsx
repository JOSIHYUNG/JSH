import type { AgentWebSource } from '../../domain/agent'

export function WebSourceCard({ source }: { source: AgentWebSource }) {
  return (
    <a className="web-source-card" href={source.url} target="_blank" rel="noreferrer noopener">
      <span className="source-rank">{source.citation_key}</span>
      <span className="source-body"><strong>{source.title ?? source.url}</strong><span>{source.publisher ?? source.url}</span><small>웹 검색 출처 · 새 탭에서 열기</small></span>
      <span className="web-source-arrow" aria-hidden="true">↗</span>
    </a>
  )
}
