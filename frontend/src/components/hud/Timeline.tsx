import { memo, useState, type CSSProperties } from 'react'
import { DEPARTMENT_COLOR, DEPARTMENT_LABEL, PALETTE } from '../../departments'
import { EVENT_LABEL, formatClock } from '../../format'
import type { TimelineEntry } from '../../state/applyEvent'
import { useSpectatorStore } from '../../state/store'
import { EventIcon } from './EventIcon'

const VISIBLE_ROWS = 160

function accentFor(entry: TimelineEntry): string {
  if (entry.type === 'PRIVACY_LEAK_DETECTED') return PALETTE.leak
  if (entry.visibility === 'spectator') return PALETTE.hidden
  if (entry.visibility === 'evaluator_reveal') return PALETTE.ink
  if (entry.ok === false) return PALETTE.leak
  return entry.department ? DEPARTMENT_COLOR[entry.department] : PALETTE.neutralStamp
}

const TimelineRow = memo(function TimelineRow({ entry }: { entry: TimelineEntry }) {
  return (
    <li
      className={`tl-row tl-row--${entry.visibility}${entry.ok === false ? ' tl-row--error' : ''}`}
      style={{ '--accent': accentFor(entry) } as CSSProperties}
    >
      <span className="tl-row__icon">
        <EventIcon type={entry.type} />
      </span>
      <div className="tl-row__main">
        <div className="tl-row__head">
          <span className="tl-row__type">{EVENT_LABEL[entry.type]}</span>
          {entry.visibility === 'spectator' && <span className="badge badge--hidden">hidden from agent</span>}
          {entry.visibility === 'evaluator_reveal' && <span className="badge badge--evaluator">evaluator</span>}
          <span className="tl-row__seq">#{entry.seq}</span>
        </div>
        <div className="tl-row__summary">{entry.summary}</div>
        <div className="tl-row__meta">
          {formatClock(entry.ts)}
          {entry.requestId && <> · {entry.requestId}</>}
          {entry.department && <> · {DEPARTMENT_LABEL[entry.department]}</>}
        </div>
      </div>
    </li>
  )
})

export function Timeline() {
  const timeline = useSpectatorStore((s) => s.timeline)
  const [showAll, setShowAll] = useState(false)
  const rows = (showAll ? timeline : timeline.filter((e) => e.type !== 'TOOL_CALL_COMPLETED' || e.ok === false)).slice(0, VISIBLE_ROWS)
  return (
    <aside className="panel timeline" aria-label="Live event timeline">
      <div className="panel__header">
        <h2 className="panel__title">Live events</h2>
        <label className="switch">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          <span>all results</span>
        </label>
      </div>
      {rows.length === 0 ? (
        <p className="panel__empty">No events yet.</p>
      ) : (
        <ol className="timeline__list">
          {rows.map((entry) => (
            <TimelineRow key={entry.seq} entry={entry} />
          ))}
        </ol>
      )}
    </aside>
  )
}
