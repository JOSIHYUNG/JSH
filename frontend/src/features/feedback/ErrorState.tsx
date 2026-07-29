import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'

export function ErrorState({ title = '불러오지 못했습니다', message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return <div className="error-state"><span className="error-icon"><Icon name="alert" /></span><div><h3>{title}</h3><p>{message}</p>{onRetry && <Button variant="ghost" size="sm" onClick={onRetry}><Icon name="refresh" /> 다시 시도</Button>}</div></div>
}
