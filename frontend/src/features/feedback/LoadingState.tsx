export function LoadingState({ label = '불러오는 중' }: { label?: string }) {
  return <div className="loading-state" role="status"><span className="loading-orbit" /> <span>{label}</span></div>
}
