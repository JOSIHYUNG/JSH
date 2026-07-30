import type { GraphFilters } from '../../domain/knowledge'
import { conceptTypeLabels, conceptTypeOrder } from '../../domain/knowledge'
import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'

export type GraphControlType = 'orbit' | 'trackball'

type Props = { filters: GraphFilters; onChange: (filters: GraphFilters) => void; onReset: () => void; onFit: () => void; controlType: GraphControlType; onControlTypeChange: (type: GraphControlType) => void }

export function GraphControls({ filters, onChange, onReset, onFit, controlType, onControlTypeChange }: Props) {
  return <div className="graph-controls">
    <label className="control-select"><Icon name="filter" /><span className="sr-only">관계 강도</span><select value={filters.minStrength} onChange={(event) => onChange({ ...filters, minStrength: Number(event.target.value) })}><option value="0">모든 연결</option><option value=".2">관련도 20%+</option><option value=".5">강한 연결만</option></select></label>
    <label className="control-select"><span className="sr-only">개념 유형</span><select value={filters.conceptType} onChange={(event) => onChange({ ...filters, conceptType: event.target.value as GraphFilters['conceptType'] })}><option value="all">모든 개념</option>{conceptTypeOrder.map((type) => <option key={type} value={type}>{conceptTypeLabels[type]}</option>)}</select></label>
    <label className="control-select"><span className="sr-only">최근 기간</span><select value={filters.recentDays ?? ''} onChange={(event) => onChange({ ...filters, recentDays: event.target.value ? Number(event.target.value) : null })}><option value="">전체 기간</option><option value="7">최근 7일</option><option value="30">최근 30일</option><option value="90">최근 90일</option></select></label>
    <label className="control-select control-camera"><Icon name="orbit" /><span className="sr-only">카메라 조작 방식</span><select value={controlType} onChange={(event) => onControlTypeChange(event.target.value as GraphControlType)}><option value="orbit">궤도 회전</option><option value="trackball">자유 회전</option></select></label>
    <span className="graph-control-hint">배경 드래그 회전 · 우클릭 이동 · 휠 확대</span>
    <label className="control-toggle"><input type="checkbox" checked={filters.includeChunks} onChange={(event) => onChange({ ...filters, includeChunks: event.target.checked })} /><span>청크 보기</span></label>
    <Button variant="ghost" size="sm" onClick={onReset}>초기화</Button><Button variant="ghost" size="sm" onClick={onFit}><Icon name="orbit" /> 전체 보기</Button>
  </div>
}
