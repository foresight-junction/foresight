import { describe, expect, it } from 'vitest'
import { applyEvent, applyEvents, createInitialState, type ViewState } from '../state/applyEvent'
import type { ObservationEvent } from '../types'
import { FIXTURE_EPISODE, fixtureEpisode, makeEvent, withoutLiveReveal } from './fixture'

function upTo(seq: number, events: ObservationEvent[] = fixtureEpisode()): ViewState {
  return applyEvents(
    createInitialState(),
    events.filter((e) => e.seq <= seq),
  )
}

describe('request lifecycle', () => {
  it('tracks a request from arrival to decision and hands over to the next one', () => {
    const received = upTo(3)
    expect(received.currentRequestId).toBe('R-001')
    expect(received.queue).toEqual({ position: 1, total: 3 })
    const r1 = received.requests['R-001']
    expect(r1.kind).toBe('lookup')
    expect(r1.requester).toEqual({ id: 'Q-0001', type: 'bank' })
    expect(r1.subjectInitials).toBe('A.V.')
    expect(r1.requestedFields).toEqual(['full_name', 'date_of_birth', 'phone'])
    expect(r1.toolCallIds).toEqual(['c-0001'])
    expect(r1.decision).toBeNull()

    const decided = upTo(14)
    expect(decided.requests['R-001'].decision).toMatchObject({
      action: 'RELEASE',
      fields: ['full_name', 'date_of_birth'],
      personCount: 1,
      responseIndex: 1,
    })
    expect(decided.requests['R-001'].toolCallIds).toEqual(['c-0001', 'c-0002', 'c-0003', 'c-0004'])
    expect(decided.lastDecision).toMatchObject({ requestId: 'R-001', action: 'RELEASE' })

    const next = upTo(18)
    expect(next.currentRequestId).toBe('R-002')
    expect(next.requestOrder).toEqual(['R-001', 'R-002'])
    expect(next.queue).toEqual({ position: 2, total: 3 })
    expect(next.requests['R-001'].toolCallIds).not.toContain('c-0005')
    expect(next.requests['R-002'].toolCallIds).toEqual(['c-0005'])
    expect(next.requests['R-001'].decision?.action).toBe('RELEASE')
  })

  it('reads episode info and the final summary', () => {
    const state = upTo(29)
    expect(state.episode).toMatchObject({ id: FIXTURE_EPISODE, scenario: 'test-slice', totalRequests: 3, profile: 'test' })
    expect(state.finalSummary).toMatchObject({ answered: 2, total: 3, criticalLeaks: 1 })
    expect(state.score?.source).toBe('final')
  })
})

describe('avatar department mapping', () => {
  it('walks to the department of each tool call and ignores hidden and evaluator events', () => {
    const state = upTo(26)
    expect(state.avatar.moves.map((m) => m.department)).toEqual([
      'registry',
      'protection',
      'decision',
      'reception',
      'protection',
      'identity',
      'decision',
    ])
    expect(state.avatar.moveCount).toBe(7)
  })

  it('does not move on STATE_CHANGED or REWARD_UPDATED', () => {
    const events = fixtureEpisode()
    const before = upTo(12, events)
    const after = applyEvents(
      before,
      events.filter((e) => e.seq >= 13 && e.seq <= 15),
    )
    expect(before.avatar.target).toBe('decision')
    expect(after.lastSeq).toBe(15)
    expect(after.avatar).toBe(before.avatar)
  })

  it('records the move index a folder must wait for', () => {
    const state = upTo(26)
    const r1 = state.requests['R-001']
    expect(r1.receivedMoveIndex).toBe(-1)
    expect(r1.decision?.moveIndex).toBe(2)
    expect(state.requests['R-002'].receivedMoveIndex).toBe(3)
    expect(state.requests['R-002'].decision?.moveIndex).toBe(6)
  })

  it('maps the tool name when department is missing', () => {
    const state = applyEvent(
      createInitialState(),
      makeEvent(1, 'TOOL_CALL_STARTED', { args_summary: null }, { tool: 'count_residents', call_id: 'x-1' }),
    )
    expect(state.avatar.target).toBe('statistics')
    expect(state.departments.statistics.active).toBe(1)
  })
})

describe('tool pulses pair start and completion by call_id', () => {
  it('raises and settles the department pulse', () => {
    const started = upTo(8)
    expect(started.departments.protection).toMatchObject({ active: 1, calls: 1, lastStartedSeq: 8 })
    expect(started.toolCalls['c-0003'].status).toBe('running')
    const completed = upTo(10)
    expect(completed.departments.protection).toMatchObject({ active: 0, lastCompletedSeq: 10, errors: 0 })
    expect(completed.toolCalls['c-0003']).toMatchObject({ status: 'ok', durationMs: 3, semantic: 'PROTECTION_CHECK' })
  })

  it('flags failed calls', () => {
    const state = upTo(23)
    expect(state.departments.identity).toMatchObject({ active: 0, errors: 1, lastErrorSeq: 23 })
    expect(state.toolCalls['c-0007']).toMatchObject({ status: 'error', errorCode: 'INVALID_ARGUMENT' })
  })

  it('uses the call_id, not the completion event department, to settle overlapping calls', () => {
    let state = createInitialState()
    state = applyEvent(
      state,
      makeEvent(1, 'TOOL_CALL_STARTED', { args_summary: null }, { department: 'registry', tool: 'get_person', call_id: 'a' }),
    )
    state = applyEvent(
      state,
      makeEvent(2, 'TOOL_CALL_STARTED', { args_summary: null }, { department: 'protection', tool: 'check_protection', call_id: 'b' }),
    )
    state = applyEvent(
      state,
      makeEvent(3, 'TOOL_CALL_COMPLETED', { ok: true, error_code: null, duration_ms: 1 }, { department: null, tool: null, call_id: 'a' }),
    )
    expect(state.departments.registry.active).toBe(0)
    expect(state.departments.protection.active).toBe(1)
    state = applyEvent(
      state,
      makeEvent(
        4,
        'TOOL_CALL_COMPLETED',
        { ok: true, error_code: null, duration_ms: 1 },
        { department: 'registry', tool: 'get_person', call_id: 'a' },
      ),
    )
    expect(state.departments.registry.active).toBe(0)
    state = applyEvent(
      state,
      makeEvent(
        5,
        'TOOL_CALL_COMPLETED',
        { ok: true, error_code: null, duration_ms: 1 },
        { department: 'protection', tool: 'check_protection', call_id: 'unknown' },
      ),
    )
    expect(state.departments.protection.active).toBe(1)
  })
})

describe('persons and STATE_CHANGED', () => {
  it('marks a person protected and hidden from the agent on sno_activated', () => {
    const state = upTo(13)
    const person = state.persons['P-0003']
    expect(person.sno).toBe('ACTIVE')
    expect(person.snoHidden).toBe(true)
    expect(state.lastStateChange).toMatchObject({ seq: 13, change: 'sno_activated', department: 'protection' })
    expect(state.departments.protection.lastHiddenSeq).toBe(13)
    expect(state.timeline[0]).toMatchObject({ seq: 13, visibility: 'spectator' })
  })

  it('keeps an SNO the agent already saw as not hidden', () => {
    let state = createInitialState()
    const person = { id: 'P-0100', initials: 'Z.Z.' }
    state = applyEvent(
      state,
      makeEvent(1, 'PROTECTION_CHECK', { person, sno: 'ACTIVE' }, { department: 'protection', tool: 'check_protection', call_id: 'c' }),
    )
    state = applyEvent(
      state,
      makeEvent(
        2,
        'STATE_CHANGED',
        { change: 'sno_activated', person, case_id: null },
        { visibility: 'spectator', department: 'protection' },
      ),
    )
    expect(state.persons['P-0100']).toMatchObject({ sno: 'ACTIVE', snoHidden: false })
  })

  it('links household members', () => {
    const state = upTo(21)
    expect(state.households['H-01'].memberIds).toEqual(['P-0003', 'P-0011'])
    expect(state.persons['P-0011'].householdId).toBe('H-01')
    expect(state.persons['P-0003'].sno).toBe('ACTIVE')
  })
})

describe('verdicts come only from evaluator_reveal events', () => {
  it('keeps a decision neutral until REWARD_UPDATED reveals it', () => {
    const decided = upTo(14)
    expect(decided.requests['R-001'].verdict).toBeNull()
    expect(decided.score).toBeNull()
    const revealed = upTo(15)
    expect(revealed.requests['R-001'].verdict).toMatchObject({ correct: true, leak: 'none' })
    expect(revealed.liveReveal).toBe(true)
    expect(revealed.score).toMatchObject({ source: 'live', score: 0.2 })
  })

  it('records leaks against the request and its requester type', () => {
    const state = upTo(28)
    expect(state.requests['R-002'].verdict).toMatchObject({ correct: false, leak: 'critical' })
    expect(state.lastLeak).toMatchObject({ severity: 'critical', requesterType: 'courier', fields: ['street_address', 'postcode'] })
    expect(state.persons['P-0003'].leaked).toBe('critical')
  })

  it('leaves per-request verdicts unknown when only the final event arrives', () => {
    const events = withoutLiveReveal(fixtureEpisode())
    const state = applyEvents(createInitialState(), events)
    expect(state.finalSummary).not.toBeNull()
    expect(state.liveReveal).toBe(false)
    expect(Object.values(state.requests).every((r) => r.verdict === null)).toBe(true)
    expect(state.score?.source).toBe('final')
  })

  it('ignores a reward update that is not marked evaluator_reveal', () => {
    const base = upTo(14)
    const forged = makeEvent(
      15,
      'REWARD_UPDATED',
      {
        score: 1,
        service: 1,
        completion: 1,
        critical_leaks: 0,
        minor_leaks: 0,
        last: { request_id: 'R-001', correct: true, leak: 'none' },
      },
      { visibility: 'agent_observable', request_id: 'R-001', department: 'decision' },
    )
    const state = applyEvent(base, forged)
    expect(state.requests['R-001'].verdict).toBeNull()
    expect(state.score).toBeNull()
  })
})

describe('seq de-duplication', () => {
  it('returns the same state for a repeated or older seq', () => {
    const events = fixtureEpisode()
    const state = upTo(10, events)
    expect(applyEvent(state, events[9])).toBe(state)
    expect(applyEvent(state, events[2])).toBe(state)
    const replayed = applyEvents(state, events.slice(0, 10))
    expect(replayed).toBe(state)
    expect(replayed.timeline).toHaveLength(10)
  })

  it('applies history and stream overlap exactly once', () => {
    const events = fixtureEpisode()
    const history = events.slice(0, 20)
    const stream = events.slice(15)
    const state = applyEvents(applyEvents(createInitialState(), history), stream)
    expect(state.lastSeq).toBe(29)
    expect(state.timeline).toHaveLength(29)
    expect(state.departments.reception.calls).toBe(2)
  })

  it('resets when a new episode starts', () => {
    const finished = upTo(29)
    const next = applyEvent(
      finished,
      makeEvent(
        1,
        'EPISODE_STARTED',
        { scenario: 'second', total_requests: 5, profile: 'test' },
        { episode_id: 'ep-next', visibility: 'spectator', department: 'reception' },
      ),
    )
    expect(next.episode?.id).toBe('ep-next')
    expect(next.requestOrder).toEqual([])
    expect(next.lastSeq).toBe(1)
    expect(next.epoch).toBe(finished.epoch + 1)
  })
})
