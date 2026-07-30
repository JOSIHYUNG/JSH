import type { SystemStatus as SystemStatusData } from '../../domain/knowledge'
import { Badge } from '../../components/primitives/Badge'
import { Icon } from '../../components/primitives/Icon'

export function SystemStatus({ status }: { status: SystemStatusData | null }) {
  const localReady = status?.database === 'ready' && status.file_storage === 'ready'
  const aiReady = Boolean(localReady && status?.openai_configured)
  const label = !status ? '상태 확인 중' : !localReady ? '로컬 저장소 점검 필요' : aiReady ? 'AI 연결됨' : '로컬 모드'
  return <div className="system-status" title={status?.vector_store_configured ? '의미 검색 인덱스 사용 가능' : '질문은 로컬 검색으로 보완됩니다.'}><span className={`status-dot ${localReady ? 'is-ready' : ''}`} /><span>{label}</span>{status && <Badge tone={aiReady ? 'success' : localReady ? 'neutral' : 'warning'}>{status.app_version}</Badge>}<Icon name="orbit" /></div>
}
