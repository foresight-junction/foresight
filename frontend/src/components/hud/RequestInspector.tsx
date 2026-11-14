import type { CSSProperties } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { DEPARTMENT_COLOR, PALETTE } from '../../departments'
import { formatArgs, humanize } from '../../format'
import type { RequestView, ToolCallView } from '../../state/applyEvent'
import { useSpectatorStore } from '../../state/store'

const NO_CALLS: ToolCallView[] = []

function VerdictChip({ request }: { request: RequestView }) {
  const leak = request.verdict?.leak && request.verdict.leak !== 'none' ? request.verdict.leak : request.leaks[0]?.severity
  if (!request.verdict && !leak) return <span className="chip chip--muted">verdict hidden until reveal</span>
  return (
    <>
      {request.verdict && (
        <span className={`chip ${request.verdict.correct ? 'chip--correct' : 'chip--incorrect'}`}>
          {request.verdict.correct ? 'correct' : 'incorrect'}
        </span>
      )}
      {leak && <span className="chip chip--leak">{leak} leak</span>}
    </>
  )
}

function CallRow({ call }: { call: ToolCallView }) {
  const color = call.department ? DEPARTMENT_COLOR[call.department] : PALETTE.neutralStamp
  const args = formatArgs(call.argsSummary)
  return (
    <li className={`call call--${call.status}`} style={{ '--accent': color } as CSSProperties}>
      <span className="call__dot" />
      <span className="call__tool">{call.tool ?? 'tool'}</span>
      {args && (
        <span className="call__args" title={args}>
          {args}
        </span>
      )}
      <span className="call__status">
        {call.status === 'running' && <span className="spinner" aria-label="running" />}
        {call.status === 'ok' && `${Math.round(call.durationMs ?? 0)} ms`}
        {call.status === 'error' && (call.errorCode ?? 'error')}
      </span>
    </li>
  )
}

export function RequestInspector() {
  const request = useSpectatorStore((s) => (s.currentRequestId ? s.requests[s.currentRequestId] : undefined))
  const calls = useSpectatorStore(
    useShallow((s) => {
      const current = s.currentRequestId ? s.requests[s.currentRequestId] : undefined
      if (!current) return NO_CALLS
      return current.toolCallIds.map((id) => s.toolCalls[id]).filter((c): c is ToolCallView => c !== undefined)
    }),
  )

  if (!request) {
    return (
      <section className="panel inspector" aria-label="Request inspector">
        <div className="panel__header">
          <h2 className="panel__title">Current request</h2>
        </div>
        <p className="panel__empty">Waiting for the agent to pull a request.</p>
      </section>
    )
  }

  const decision = request.decision
  return (
    <section className="panel inspector" aria-label="Request inspector">
      <div className="panel__header">
        <h2 className="panel__title">Current request</h2>
        <span className="inspector__position">
          {request.position} / {request.total}
        </span>
      </div>
      <div className="inspector__id-row">
        <span className="mono inspector__id">{request.id}</span>
        <span className="chip chip--kind">{humanize(request.kind)}</span>
      </div>
      <dl className="facts">
        <dt>Requester</dt>
        <dd>
          {humanize(request.requester.type)} <span className="mono muted">{request.requester.id}</span>
        </dd>
        <dt>Subject</dt>
        <dd>{request.subjectInitials ?? <span className="muted">none named</span>}</dd>
        <dt>Fields</dt>
        <dd className="chips">
          {request.requestedFields.length === 0 ? (
            <span className="muted">none</span>
          ) : (
            request.requestedFields.map((field) => (
              <span key={field} className="chip chip--field">
                {field}
              </span>
            ))
          )}
        </dd>
      </dl>
      <div className="inspector__section-title">
        Tool calls <span className="muted">{calls.length}</span>
      </div>
      {calls.length === 0 ? (
        <p className="panel__empty panel__empty--small">No tool calls yet.</p>
      ) : (
        <ol className="calls">
          {calls.map((call) => (
            <CallRow key={call.callId} call={call} />
          ))}
        </ol>
      )}
      <div className="inspector__section-title">Decision</div>
      {decision ? (
        <div className={`decision decision--${decision.action.toLowerCase()}`}>
          <div className="decision__stamp">{decision.action}</div>
          <div className="decision__body">
            <div className="chips">
              {decision.fields.length === 0 ? (
                <span className="muted">no fields released</span>
              ) : (
                decision.fields.map((field) => (
                  <span key={field} className="chip chip--field">
                    {field}
                  </span>
                ))
              )}
            </div>
            <div className="muted small">
              {decision.personCount} person{decision.personCount === 1 ? '' : 's'} · response #{decision.responseIndex}
            </div>
            <div className="chips">
              <VerdictChip request={request} />
            </div>
          </div>
        </div>
      ) : (
        <p className="panel__empty panel__empty--small">Not answered yet.</p>
      )}
    </section>
  )
}
