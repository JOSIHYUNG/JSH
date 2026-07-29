import type { DocumentSummary } from '../../domain/knowledge'
import { Icon } from '../../components/primitives/Icon'
import { StatusBadge } from '../feedback/StatusBadge'

export function RecentDocuments({ documents, onOpen }: { documents: DocumentSummary[]; onOpen: (id: number) => void }) {
  return <section className="recent-documents"><div className="subsection-heading"><span>최근 자료</span><small>{documents.length} documents</small></div><div className="recent-list">{documents.slice(0, 4).map((document) => <button type="button" key={document.id} onClick={() => onOpen(document.id)}><span className="recent-icon"><Icon name="doc" /></span><span className="recent-copy"><strong>{document.title}</strong><small>{document.summary}</small></span><StatusBadge status={document.status} /></button>)}</div></section>
}
