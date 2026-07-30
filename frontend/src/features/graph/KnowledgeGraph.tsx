import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import type { ForceGraphMethods } from 'react-force-graph-3d'
import type { GraphNode, GraphSnapshot } from '../../domain/knowledge'
import { EmptyState } from '../feedback/EmptyState'
import { LoadingState } from '../feedback/LoadingState'
import { graphColor } from './graphColors'
import { GraphControls, type GraphControlType } from './GraphControls'
import { GraphLegend } from './GraphLegend'
import { GraphNodeList } from './GraphNodeList'
import { useTheme } from '../../app/themeContext'

type KnowledgeGraphProps = {
  snapshot: GraphSnapshot | null
  loading: boolean
  onNodeSelect: (node: GraphNode) => void
  onFiltersChange: (filters: GraphSnapshot['filters']) => void
  onResetFilters: () => void
  focusEntity?: { entity_type: GraphNode['entity_type']; entity_id: number } | null
  onFit?: () => void
}

export function KnowledgeGraph({ snapshot, loading, onNodeSelect, onFiltersChange, onResetFilters, focusEntity, onFit }: KnowledgeGraphProps) {
  const { theme } = useTheme()
  const graphRef = useRef<ForceGraphMethods | undefined>(undefined)
  const canvasRef = useRef<HTMLDivElement>(null)
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 560 })
  const [controlType, setControlType] = useState<GraphControlType>('orbit')
  const hasNodes = Boolean(snapshot?.nodes.length)
  const reduceMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const graphData = useMemo(() => ({
    nodes: (snapshot?.nodes ?? []).map((node) => ({ ...node, metadata: { ...node.metadata } })),
    links: (snapshot?.edges ?? []).map((edge) => ({ ...edge })),
  }), [snapshot])

  useEffect(() => {
    const element = canvasRef.current
    if (!element) return
    const updateSize = () => setCanvasSize({ width: element.clientWidth, height: element.clientHeight })
    updateSize()
    const observer = new ResizeObserver(updateSize)
    observer.observe(element)
    return () => observer.disconnect()
  }, [hasNodes, loading])

  useEffect(() => {
    if (!snapshot || !hasNodes || !canvasSize.width || focusEntity) return
    const timer = window.setTimeout(() => graphRef.current?.zoomToFit(700, 56), 300)
    return () => window.clearTimeout(timer)
  }, [canvasSize.width, controlType, focusEntity, hasNodes, snapshot])

  useEffect(() => {
    if (!focusEntity || !snapshot || !graphRef.current) return
    const target = graphData.nodes.find((node) => node.entity_type === focusEntity.entity_type && node.entity_id === focusEntity.entity_id)
    if (!target) return
    const graph = graphRef.current
    const node = target as GraphNode & { x?: number; y?: number; z?: number }
    const x = node.x ?? 0
    const y = node.y ?? 0
    const z = node.z ?? 0
    const distance = 120
    graph.cameraPosition({ x: x + distance, y: y + distance, z: z + distance }, { x, y, z }, 650)
  }, [focusEntity, graphData.nodes, snapshot])

  const fitGraph = () => {
    graphRef.current?.zoomToFit(800, 48)
    onFit?.()
  }

  return <section className="graph-section">
    <div className="section-heading"><div><span className="eyebrow">CONSTELLATION / KNOWLEDGE MAP</span><h1>지식의 <em>구조</em></h1></div><span className="section-note">드래그 · 확대 · 노드 클릭</span></div>
    <div className="graph-toolbar"><GraphLegend />{snapshot && <GraphControls filters={snapshot.filters} onChange={onFiltersChange} onReset={onResetFilters} onFit={fitGraph} controlType={controlType} onControlTypeChange={setControlType} />}</div>
    {!loading && !hasNodes && <div className="graph-empty"><EmptyState title="첫 자료를 추가해보세요" description="자료를 쌓으면 개념과 연결이 이 공간에 나타납니다." /></div>}
    {loading && <div className="graph-loading"><LoadingState label="지식 구조를 불러오는 중" /></div>}
    {!loading && hasNodes && snapshot && <>
      <div className="graph-canvas" ref={canvasRef} role="img" aria-label={`문서와 개념 ${snapshot.node_count}개, 연결 ${snapshot.edge_count}개의 3차원 지식 그래프`}>
        <ForceGraph3D
          key={controlType}
          ref={graphRef}
          graphData={graphData}
          backgroundColor={theme === 'dark' ? '#0d1726' : '#e9f0f6'}
          width={canvasSize.width}
          height={canvasSize.height}
          controlType={controlType}
          enableNavigationControls
          enableNodeDrag={false}
          enablePointerInteraction
          nodeLabel={(node: object) => (node as GraphNode).label}
          nodeColor={(node: object) => { const graphNode = node as GraphNode; return graphColor(graphNode.color_token, theme, graphNode.entity_id) }}
          nodeVal={(node: object) => (node as GraphNode).size}
          nodeRelSize={1.35}
          nodeOpacity={.96}
          nodeResolution={8}
          linkColor={() => theme === 'dark' ? 'rgba(123, 226, 212, .55)' : 'rgba(22, 140, 131, .45)'}
          linkWidth={(link: object) => Math.max(.5, (link as { strength: number }).strength * 3)}
          linkDirectionalArrowLength={(link: object) => (link as { is_directed: boolean }).is_directed ? 3 : 0}
          linkDirectionalArrowRelPos={.72}
          linkDirectionalParticles={(link: object) => reduceMotion ? 0 : (link as { is_directed: boolean }).is_directed ? 2 : 1}
          linkDirectionalParticleSpeed={.003}
          onNodeClick={(node: object) => onNodeSelect(node as GraphNode)}
          warmupTicks={30}
          cooldownTicks={120}
          cooldownTime={1800}
          d3VelocityDecay={.35}
          showNavInfo={false}
        />
      </div>
      <details className="graph-list-fallback"><summary><span>키보드로 노드 탐색</span><small>{snapshot.node_count}개</small></summary><GraphNodeList nodes={snapshot.nodes} onSelect={onNodeSelect} /></details>
    </>}
    {snapshot?.truncated && <p className="graph-truncated">일부 관계만 표시 중입니다. 필터를 조정하면 더 많은 연결을 볼 수 있습니다.</p>}
  </section>
}
