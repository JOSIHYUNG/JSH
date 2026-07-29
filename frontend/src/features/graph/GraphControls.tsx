import type { GraphFilters } from '../../domain/knowledge'
import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'

export function GraphControls({ filters, onChange, onReset, onFit }: { filters: GraphFilters; onChange: (filters: GraphFilters) => void; onReset: () => void; onFit: () => void }) {
  return <div className="graph-controls"><label><Icon name="filter" /> 필터 <select value={filters.minStrength} onChange={(event) => onChange({ ...filters, minStrength: Number(event.target.value) })}><option value="0">모든 연결</option><option value=".2">관련도 20%+</option><option value=".5">강한 연결만</option></select></label><label><span className="sr-only">개념 유형</span><select value={filters.conceptType} onChange={(event) => onChange({ ...filters, conceptType: event.target.value as GraphFilters['conceptType'] })}><option value="all">모든 개념</option><option value="technology">기술</option><option value="event">사건</option><option value="policy_law">정책·법률</option><option value="organization">조직</option><option value="person">인물</option></select></label><Button variant="ghost" size="sm" onClick={onReset}>초기화</Button><Button variant="ghost" size="sm" onClick={onFit}><Icon name="orbit" /> 전체 보기</Button></div>
}
