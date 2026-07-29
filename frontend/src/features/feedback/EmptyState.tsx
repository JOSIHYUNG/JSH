import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'

export function EmptyState({ title, description, actionLabel, onAction }: { title: string; description: string; actionLabel?: string; onAction?: () => void }) {
  return <div className="empty-state"><Icon name="spark" /><h3>{title}</h3><p>{description}</p>{actionLabel && onAction && <Button variant="primary" onClick={onAction}>{actionLabel} <Icon name="arrow" /></Button>}</div>
}
