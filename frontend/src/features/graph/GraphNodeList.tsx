import type { GraphNode } from '../../domain/knowledge'
import { Icon } from '../../components/primitives/Icon'
import { conceptTypeLabels } from '../../domain/knowledge'

export function GraphNodeList({ nodes, onSelect }: { nodes: GraphNode[]; onSelect: (node: GraphNode) => void }) {
  return <div className="graph-node-list" aria-label="그래프 노드 목록">{nodes.map((node) => <button key={node.id} type="button" onClick={() => onSelect(node)}><span className={`node-list-icon ${node.entity_type}`}><Icon name={node.entity_type === 'document' ? 'doc' : 'concept'} /></span><span><strong>{node.label}</strong><small>{node.entity_type === 'concept' && node.subtype ? conceptTypeLabels[node.subtype] : '자료 문서'} · 연결 {node.metadata.connection_count ?? 0}</small></span><Icon name="chevron" /></button>)}</div>
}
