type IconName = 'spark' | 'plus' | 'arrow' | 'history' | 'close' | 'search' | 'graph' | 'doc' | 'concept' | 'filter' | 'chevron' | 'orbit' | 'check' | 'alert' | 'refresh'

const icons: Record<IconName, string> = {
  spark: '✦', plus: '+', arrow: '↗', history: '◷', close: '×', search: '⌕', graph: '◈', doc: '▤', concept: '✺', filter: '≡', chevron: '›', orbit: '◎', check: '✓', alert: '!', refresh: '↻',
}

export function Icon({ name, label }: { name: IconName; label?: string }) {
  return <span className={`icon icon-${name}`} aria-hidden={label ? undefined : true} aria-label={label}>{icons[name]}</span>
}
