import { useState } from 'react'
import { BACKEND_URL } from '../api'
import type { ReplayControls } from '../hooks/useReplayFeed'
import { useSpectatorStore } from '../state/store'
import type { FeedMode } from '../types'
import { LeakAlerts } from './hud/LeakAlerts'
import { ReplayBar } from './hud/ReplayBar'
import { RequestInspector } from './hud/RequestInspector'
import { ScorePanel } from './hud/ScorePanel'
import { ShiftSummary } from './hud/ShiftSummary'
import { Timeline } from './hud/Timeline'
import { TopBar } from './hud/TopBar'

function EmptyState({ mode, replay }: { mode: FeedMode; replay: ReplayControls }) {
  const hasEpisode = useSpectatorStore((s) => s.episode !== null)
  const connection = useSpectatorStore((s) => s.connection)
  if (hasEpisode) return null
  if (mode === 'replay') {
    return (
      <div className="panel empty-state">
        {replay.status === 'error' ? (
          <>
            <h2>Replay could not be loaded</h2>
            <p>{replay.error}</p>
            <p className="muted small">
              Put an exported <span className="mono">/observe/history</span> JSON array under <span className="mono">frontend/public/</span>{' '}
              and open <span className="mono">?replay=&lt;file&gt;.json</span>.
            </p>
          </>
        ) : (
          <>
            <h2>Loading replay</h2>
            <p className="mono small">{replay.path}</p>
          </>
        )}
      </div>
    )
  }
  return (
    <div className="panel empty-state">
      <h2>Waiting for an episode</h2>
      <p>
        Listening to <span className="mono">{BACKEND_URL}/observe/stream</span>
      </p>
      <p className="muted small">
        Status: {connection.state}
        {connection.detail && connection.detail !== BACKEND_URL ? ` · ${connection.detail}` : ''}
      </p>
    </div>
  )
}

export function Hud({ mode, replay }: { mode: FeedMode; replay: ReplayControls }) {
  const finishedSeq = useSpectatorStore((s) => s.finalSummary?.seq ?? null)
  const [dismissedSeq, setDismissedSeq] = useState<number | null>(null)
  const [reopened, setReopened] = useState(false)
  const summaryOpen = finishedSeq !== null && (dismissedSeq !== finishedSeq || reopened)

  return (
    <div className="hud">
      <TopBar mode={mode} onOpenSummary={() => setReopened(true)} />
      <div className="hud__left">
        <RequestInspector />
        <ScorePanel />
      </div>
      <Timeline />
      {mode === 'replay' && <ReplayBar replay={replay} />}
      <LeakAlerts />
      <EmptyState mode={mode} replay={replay} />
      {summaryOpen && (
        <ShiftSummary
          onClose={() => {
            setDismissedSeq(finishedSeq)
            setReopened(false)
          }}
        />
      )}
    </div>
  )
}
