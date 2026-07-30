import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { failed: boolean }

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // The screen remains recoverable without exposing document data in logs.
  }

  render() {
    if (this.state.failed) {
      return <main className="fatal-state">
        <span>JSH / SECOND BRAIN</span>
        <h1>화면을 표시하지 못했습니다</h1>
        <p>입력한 자료는 백엔드에 보존되어 있습니다. 화면을 새로 불러와 다시 연결해 주세요.</p>
        <button type="button" onClick={() => window.location.reload()}>화면 새로고침</button>
      </main>
    }
    return this.props.children
  }
}
