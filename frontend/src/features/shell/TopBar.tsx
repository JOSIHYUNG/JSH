import { Button } from '../../components/primitives/Button'
import { Icon } from '../../components/primitives/Icon'
import type { SystemStatus as SystemStatusData } from '../../domain/knowledge'
import { useTheme } from '../../app/themeContext'
import { SystemStatus } from './SystemStatus'

export function TopBar({ status, onAdd, onHistory }: { status: SystemStatusData | null; onAdd: () => void; onHistory: () => void }) {
  const { theme, toggleTheme } = useTheme()
  const nextTheme = theme === 'dark' ? 'light' : 'dark'
  return <header className="topbar">
    <button className="brand" type="button" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
      <span className="brand-mark"><Icon name="spark" /></span>
      <span><b>JSH</b><small>SECOND BRAIN</small></span>
    </button>
    <div className="topbar-actions">
      <SystemStatus status={status} />
      <Button variant="ghost" size="sm" className="theme-toggle" onClick={toggleTheme} aria-label={`Switch to ${nextTheme} mode`} title={`Switch to ${nextTheme} mode`} aria-pressed={theme === 'light'}>
        <Icon name={theme === 'dark' ? 'sun' : 'moon'} /><span className="theme-toggle-label">{theme === 'dark' ? 'Light' : 'Dark'}</span>
      </Button>
      <Button variant="ghost" size="sm" onClick={onHistory}><Icon name="history" /> 대화 기록</Button>
      <Button variant="primary" size="sm" onClick={onAdd}><Icon name="plus" /> 자료 추가</Button>
    </div>
  </header>
}
