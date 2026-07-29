import { useRef } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import type { ForceGraphMethods } from 'react-force-graph-3d'
import type { GraphNode, GraphSnapshot } from '../../domain/knowledge'
import { EmptyState } from '../feedback/EmptyState'
import { LoadingState } from '../feedback/LoadingState'
import { graphColor } from './graphColors'
import { GraphControls } from './GraphControls'
import { GraphLegend } from './GraphLegend'
import { GraphNodeList } from './GraphNodeList'

type KnowledgeGraphProps = {
  snapshot: GraphSnapshot | null
  loading: boolean
  onNodeSelect: (node: GraphNode) => void
  onFiltersChange: (filters: GraphSnapshot['filters']) => void
  onResetFilters: () => void
  onFit?: () => void
}

export function KnowledgeGraph({ snapshot, loading, onNodeSelect, onFiltersChange, onResetFilters, onFit }: KnowledgeGraphProps) {
  const graphRef = useRef<ForceGraphMethods | undefined>(undefined)
  const hasNodes = Boolean(snapshot?.nodes.length)

  const fitGraph = () => {
    graphRef.current?.zoomToFit(800, 48)
    onFit?.()
  }

  return <section className="graph-section">
    <div className="section-heading"><div><span className="eyebrow">CONSTELLATION / KNOWLEDGE MAP</span><h1>지식의 <em>구조</em></h1></div><span className="section-note">드래그 · 확대 · 노드 클릭</span></div>
    <div className="graph-toolbar"><GraphLegend />{snapshot && <GraphControls filters={snapshot.filters} onChange={onFiltersChange} onReset={onResetFilters} onFit={fitGraph} />}</div>
    {loading && <div className="graph-loading"><LoadingState label="지식 구조를 불러오는 중" /></div>}
    {!loading && !hasNodes && <div className="graph-empty"><EmptyState title="첫 자료를 추가해보세요" description="자료를 쌓으면 개념과 연결이 이 공간에 나타납니다." /></div>}
    {!loading && hasNodes && snapshot && <>
      <div className="graph-canvas"><ForceGraph3D ref={graphRef} graphData={{ nodes: snapshot.nodes, links: snapshot.edges }} backgroundColor="#07111E" nodeLabel={(node: object) => (node as GraphNode).label} nodeColor={(node: object) => graphColor((node as GraphNode).color_token)} nodeRelSize={5} linkColor={() => 'rgba(123, 226, 212, .45)'} linkWidth={(link: object) => Math.max(.5, (link as { strength: number }).strength * 3)} linkDirectionalParticles={2} linkDirectionalParticleSpeed={.003} onNodeClick={(node: object) => onNodeSelect(node as GraphNode)} showNavInfo={false} height={520} /></div>
      <div className="graph-list-fallback"><div className="subsection-heading"><span>노드 목록</span><small>{snapshot.node_count}개 표시</small></div><GraphNodeList nodes={snapshot.nodes} onSelect={onNodeSelect} /></div>
    </>}
    {snapshot?.truncated && <p className="graph-truncated">일부 관계만 표시 중입니다. 필터를 조정하면 더 많은 연결을 볼 수 있습니다.</p>}
  </section>
}
