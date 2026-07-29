import { Badge } from '../../components/primitives/Badge'
import { Icon } from '../../components/primitives/Icon'
import type { QuestionSource } from '../../domain/knowledge'

export function SourceCard({ source, onOpen }: { source: QuestionSource; onOpen: (source: QuestionSource) => void }) {
  return <button type="button" className={`source-card ${source.openable ? '' : 'is-stale'}`} onClick={() => onOpen(source)} disabled={!source.openable}><span className="source-rank">{source.citation_key}</span><span className="source-body"><strong>{source.document_title}</strong><span>{source.chunk_preview}</span><small><Badge tone={source.openable ? 'amber' : 'warning'}>{source.openable ? `청크 ${source.rank}` : '당시 근거'}</Badge> · 관련도 {Math.round(source.score * 100)}%</small></span><Icon name={source.openable ? 'arrow' : 'alert'} /></button>
}
