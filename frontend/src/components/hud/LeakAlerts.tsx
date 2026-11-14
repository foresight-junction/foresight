import { leakSentence } from '../../format'
import { useSpectatorStore } from '../../state/store'

export function LeakAlerts() {
  const leak = useSpectatorStore((s) => s.lastLeak)
  if (!leak) return null
  return (
    <>
      {leak.severity === 'critical' && <div key={`vignette-${leak.seq}`} className="alarm-vignette" aria-hidden="true" />}
      <div key={`toast-${leak.seq}`} className={`leak-toast leak-toast--${leak.severity}`} role="status">
        <span className="leak-toast__label">{leak.severity === 'critical' ? 'Critical leak' : 'Minor leak'}</span>
        <span className="leak-toast__text">{leakSentence(leak.severity, leak.fields, leak.persons, leak.requesterType)}</span>
        {leak.requestId && <span className="mono leak-toast__id">{leak.requestId}</span>}
        <span className="badge badge--evaluator">evaluator</span>
      </div>
    </>
  )
}
