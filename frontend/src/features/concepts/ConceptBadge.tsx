import { Badge } from '../../components/primitives/Badge'
import type { ConceptType } from '../../domain/knowledge'
import { conceptTypeLabels } from '../../domain/knowledge'

export function ConceptBadge({ type }: { type: ConceptType }) {
  const tone = type === 'technology' || type === 'system' ? 'teal' : type === 'event' ? 'danger' : type === 'policy_law' ? 'success' : type === 'person' ? 'violet' : 'amber'
  return <Badge tone={tone}>{conceptTypeLabels[type]}</Badge>
}
