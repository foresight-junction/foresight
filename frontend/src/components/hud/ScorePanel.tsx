import { formatPercent, formatScore } from '../../format'
import { useSpectatorStore } from '../../state/store'

export function ScorePanel() {
  const score = useSpectatorStore((s) => s.score)
  return (
    <section className="panel score" aria-label="Score">
      <div className="panel__header">
        <h2 className="panel__title">Score</h2>
        {score && (
          <span className={`badge ${score.source === 'final' ? 'badge--final' : 'badge--evaluator'}`}>
            {score.source === 'final' ? 'final' : 'live reveal'}
          </span>
        )}
      </div>
      {score ? (
        <>
          <div className="score__value">{formatScore(score.score)}</div>
          <div className="score__grid">
            <div className="metric">
              <span className="metric__label">Service</span>
              <span className="metric__value">{formatPercent(score.service)}</span>
            </div>
            <div className="metric">
              <span className="metric__label">Completion</span>
              <span className="metric__value">{formatPercent(score.completion)}</span>
            </div>
            <div className={`metric${score.criticalLeaks > 0 ? ' metric--critical' : ''}`}>
              <span className="metric__label">Critical leaks</span>
              <span className="metric__value">{score.criticalLeaks}</span>
            </div>
            <div className={`metric${score.minorLeaks > 0 ? ' metric--minor' : ''}`}>
              <span className="metric__label">Minor leaks</span>
              <span className="metric__value">{score.minorLeaks}</span>
            </div>
          </div>
        </>
      ) : (
        <div className="score__pending">
          <div className="score__value score__value--muted">—</div>
          <p>revealed at finalize</p>
        </div>
      )}
      <ul className="legend" aria-label="Legend">
        <li>
          <span className="swatch swatch--neutral" />
          decided
        </li>
        <li>
          <span className="swatch swatch--correct" />
          correct
        </li>
        <li>
          <span className="swatch swatch--incorrect" />
          incorrect
        </li>
        <li>
          <span className="swatch swatch--leak" />
          leak
        </li>
        <li>
          <span className="swatch swatch--hidden" />
          hidden state
        </li>
      </ul>
    </section>
  )
}
