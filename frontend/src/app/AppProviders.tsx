import type { PropsWithChildren } from 'react'
import { AppErrorBoundary } from './AppErrorBoundary'
import { ThemeProvider } from './ThemeProvider'

export function AppProviders({ children }: PropsWithChildren) {
  return <AppErrorBoundary><ThemeProvider>{children}</ThemeProvider></AppErrorBoundary>
}
