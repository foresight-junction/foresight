import { REPLAY_SPEEDS, type ReplayControls } from '../../hooks/useReplayFeed'

export function ReplayBar({ replay }: { replay: ReplayControls }) {
  const progress = replay.total > 0 ? (replay.cursor / replay.total) * 100 : 0
  const canPlay = replay.status === 'paused' || replay.status === 'playing'
  return (
    <div className="panel replay" aria-label="Replay controls">
      {canPlay ? (
        <button
          className="icon-btn"
          onClick={replay.status === 'playing' ? replay.pause : replay.play}
          aria-label={replay.status === 'playing' ? 'Pause' : 'Play'}
        >
          {replay.status === 'playing' ? (
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <rect x="6" y="5" width="4" height="14" rx="1" />
              <rect x="14" y="5" width="4" height="14" rx="1" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8 5l11 7-11 7z" />
            </svg>
          )}
        </button>
      ) : (
        <span className="replay__state">{replay.status}</span>
      )}
      <button className="icon-btn" onClick={replay.restart} aria-label="Restart replay" disabled={replay.total === 0}>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 12a7 7 0 1 0 2.1-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          <path d="M4 4v4.5h4.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      <div className="replay__track" aria-hidden="true">
        <div className="replay__fill" style={{ width: `${progress}%` }} />
      </div>
      <span className="replay__count mono">
        {replay.cursor}/{replay.total}
      </span>
      <label className="replay__speed">
        <span className="sr-only">Playback speed</span>
        <select value={replay.speed} onChange={(e) => replay.setSpeed(Number(e.target.value))}>
          {REPLAY_SPEEDS.map((speed) => (
            <option key={speed} value={speed}>
              {speed}×
            </option>
          ))}
        </select>
      </label>
      <label className="switch">
        <input type="checkbox" checked={replay.skipIdle} onChange={(e) => replay.setSkipIdle(e.target.checked)} />
        <span>skip idle</span>
      </label>
    </div>
  )
}
