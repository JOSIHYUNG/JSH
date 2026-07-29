import type { PropsWithChildren } from 'react'

export function Badge({ children, tone = 'neutral', className = '' }: PropsWithChildren<{ tone?: 'neutral' | 'teal' | 'amber' | 'violet' | 'success' | 'warning' | 'danger'; className?: string }>) {
  return <span className={`badge badge-${tone} ${className}`}>{children}</span>
}
