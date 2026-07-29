import { Badge } from '../../components/primitives/Badge'
import { Icon } from '../../components/primitives/Icon'

export function GraphLegend() {
  return <div className="graph-legend"><span><i className="legend-dot legend-document" /> 문서</span><span><i className="legend-dot legend-concept" /> 개념</span><span><i className="legend-line" /> 관계</span><Badge tone="neutral"><Icon name="orbit" /> 3D 탐색</Badge></div>
}
