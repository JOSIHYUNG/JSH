import type { ButtonHTMLAttributes, PropsWithChildren } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

export function Button({ variant = 'secondary', size = 'md', type = 'button', children, className = '', ...props }: PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' }>) {
  return <button type={type} className={`button button-${variant} button-${size} ${className}`} {...props}>{children}</button>
}
