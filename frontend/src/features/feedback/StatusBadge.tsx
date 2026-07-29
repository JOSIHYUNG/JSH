import { Badge } from '../../components/primitives/Badge'
import type { DocumentStatus, QuestionStatus } from '../../domain/knowledge'

export function StatusBadge({ status }: { status: DocumentStatus | QuestionStatus }) {
  const map: Record<string, { label: string; tone: 'neutral' | 'teal' | 'amber' | 'violet' | 'success' | 'warning' | 'danger' }> = {
    ready: { label: '준비됨', tone: 'success' }, processing: { label: '분석 중', tone: 'teal' }, queued: { label: '대기 중', tone: 'neutral' }, retrieving: { label: '자료 찾는 중', tone: 'teal' }, generating: { label: '답변 생성 중', tone: 'violet' }, completed: { label: '완료', tone: 'success' }, no_evidence: { label: '근거 부족', tone: 'warning' }, failed: { label: '실패', tone: 'danger' }, draft: { label: '임시 보관', tone: 'neutral' }, deleting: { label: '삭제 중', tone: 'danger' }, canceled: { label: '취소됨', tone: 'warning' }, cancel_requested: { label: '취소 요청', tone: 'warning' },
  }
  const item = map[status] ?? { label: status, tone: 'neutral' as const }
  return <Badge tone={item.tone}>{item.label}</Badge>
}
