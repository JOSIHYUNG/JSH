import type { SystemStatus as SystemStatusData } from '../../domain/knowledge'
import { Badge } from '../../components/primitives/Badge'
import { Icon } from '../../components/primitives/Icon'

export function SystemStatus({ status }: { status: SystemStatusData | null }) {
  const ready = status?.database === 'ready' && status.file_storage === 'ready' && status.openai_configured
  return <div className="system-status"><span className={`status-dot ${ready ? 'is-ready' : ''}`} /><span>{ready ? 'AI 연결됨' : '설정 확인 필요'}</span>{status && <Badge tone={ready ? 'success' : 'warning'}>{status.app_version}</Badge>}<Icon name="orbit" /></div>
}
