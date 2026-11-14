import { useShallow } from 'zustand/react/shallow'
import { formatPercent, formatScore, humanize } from '../../format'
import type { RequestView } from '../../state/applyEvent'
import { useSpectatorStore } from '../../state/store'

function leakOf(request: RequestView): string | null {
  if (request.verdict && request.verdict.leak !== 'none') return request.verdict.leak
  if (request.leaks.some((l) => l.severity === 'critical')) return 'critical'
  if (request.leaks.length > 0) return 'minor'
  return request.verdict ? 'none' : null
}

export function ShiftSummary({ onClose }: { onClose: () => void }) {
  const final = useSpectatorStore((s) => s.finalSummary)
  const episode = useSpectatorStore((s) => s.episode)
  const requests = useSpectatorStore(
    useShallow((s) => s.requestOrder.map((id) => s.requests[id]).filter((r): r is RequestView => r !== undefined)),
  )
  if (!final) return null
  const itemized = requests.some((r) => r.verdict !== null)

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal panel" role="dialog" aria-modal="true" aria-labelledby="summary-title" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <div>
            <h2 id="summary-title" className="modal__title">
              Shift summary
            </h2>
            <div className="muted small">
              {episode?.id} · {episode?.scenario ?? 'scenario unknown'} · {final.answered}/{final.total} answered
            </div>
          </div>
          <button className="btn btn--ghost" onClick={onClose} aria-label="Close summary">
            Close
          </button>
        </div>
        <div className="summary__scores">
          <div className="summary__score">
            <span className="metric__label">Final score</span>
            <span className="summary__score-value">{formatScore(final.score)}</span>
          </div>
          <div className="metric">
            <span className="metric__label">Service</span>
            <span className="metric__value">{formatPercent(final.service)}</span>
          </div>
          <div className="metric">
            <span className="metric__label">Completion</span>
            <span className="metric__value">{formatPercent(final.completion)}</span>
          </div>
          <div className={`metric${final.criticalLeaks > 0 ? ' metric--critical' : ''}`}>
            <span className="metric__label">Critical leaks</span>
            <span className="metric__value">{final.criticalLeaks}</span>
          </div>
          <div className={`metric${final.minorLeaks > 0 ? ' metric--minor' : ''}`}>
            <span className="metric__label">Minor leaks</span>
            <span className="metric__value">{final.minorLeaks}</span>
          </div>
        </div>
        {!itemized && (
          <p className="summary__note">
            Per-request verdicts were not revealed during this run. The final event carries totals only, so rows stay neutral.
          </p>
        )}
        <div className="summary__table-wrap">
          <table className="summary__table">
            <thead>
              <tr>
                <th>#</th>
                <th>Request</th>
                <th>Kind</th>
                <th>Requester</th>
                <th>Decision</th>
                <th>Verdict</th>
                <th>Leak</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => {
                const leak = leakOf(r)
                return (
                  <tr key={r.id}>
                    <td className="muted">{r.position}</td>
                    <td className="mono">{r.id}</td>
                    <td>{humanize(r.kind)}</td>
                    <td>{humanize(r.requester.type)}</td>
                    <td>
                      {r.decision ? (
                        <span className={`chip chip--action chip--${r.decision.action.toLowerCase()}`}>{r.decision.action}</span>
                      ) : (
                        <span className="muted">unanswered</span>
                      )}
                    </td>
                    <td>
                      {r.verdict ? (
                        <span className={`chip ${r.verdict.correct ? 'chip--correct' : 'chip--incorrect'}`}>
                          {r.verdict.correct ? 'correct' : 'incorrect'}
                        </span>
                      ) : (
                        <span className="muted">not itemized</span>
                      )}
                    </td>
                    <td>
                      {leak === null ? (
                        <span className="muted">—</span>
                      ) : leak === 'none' ? (
                        <span className="muted">none</span>
                      ) : (
                        <span className="chip chip--leak">{leak}</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
