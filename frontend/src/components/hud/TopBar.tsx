import { useSpectatorStore } from '../../state/store'
import type { ConnectionState, FeedMode } from '../../types'

const CONNECTION_LABEL: Record<ConnectionState, string> = {
  idle: 'idle',
  connecting: 'connecting',
  connected: 'connected',
  reconnecting: 'reconnecting',
  disconnected: 'disconnected',
  error: 'error',
}

export function TopBar({ mode, onOpenSummary }: { mode: FeedMode; onOpenSummary: () => void }) {
  const episode = useSpectatorStore((s) => s.episode)
  const connection = useSpectatorStore((s) => s.connection)
  const queue = useSpectatorStore((s) => s.queue)
  const answered = useSpectatorStore((s) => s.requestOrder.reduce((n, id) => (s.requests[id]?.decision ? n + 1 : n), 0))
  const finished = useSpectatorStore((s) => s.finalSummary !== null)
  const total = queue.total ?? episode?.totalRequests ?? null
  const progress = total ? Math.min(100, (answered / total) * 100) : 0

  return (
    <header className="panel topbar">
      <div className="brand">
        <span className="brand__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M12 3l8 3v6c0 4.5-3.5 7.8-8 9-4.5-1.2-8-4.5-8-9V6z" />
          </svg>
        </span>
        <div>
          <div className="brand__name">Unfindable</div>
          <div className="brand__sub">Population register office · spectator</div>
        </div>
      </div>
      <dl className="topbar__facts">
        <div>
          <dt>Episode</dt>
          <dd className="mono">{episode?.id ?? '—'}</dd>
        </div>
        <div>
          <dt>Scenario</dt>
          <dd>{episode?.scenario ?? '—'}</dd>
        </div>
        {episode?.profile && (
          <div>
            <dt>Profile</dt>
            <dd>{episode.profile}</dd>
          </div>
        )}
      </dl>
      <div className="topbar__progress">
        <div className="topbar__progress-label">
          <span>
            Request <strong>{queue.position > 0 ? queue.position : '—'}</strong> / {total ?? '—'}
          </span>
          <span className="muted">{answered} answered</span>
        </div>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>
      <div className="topbar__status">
        <span className={`conn conn--${connection.state}`} title={connection.detail ?? undefined}>
          <span className="conn__dot" />
          {CONNECTION_LABEL[connection.state]}
        </span>
        <span className={`mode-badge mode-badge--${mode}`}>{mode === 'live' ? 'LIVE' : 'REPLAY'}</span>
        {finished && (
          <button className="btn btn--primary" onClick={onOpenSummary}>
            Shift summary
          </button>
        )}
      </div>
    </header>
  )
}
