import { DEPARTMENTS, departmentForTool } from '../departments'
import { describeEvent } from '../format'
import type {
  ArgsSummary,
  ConnectionInfo,
  DecisionAction,
  Department,
  EventType,
  LeakLevel,
  LeakSeverity,
  ObservationEvent,
  PersonRef,
  RequestKind,
  RequesterRef,
  SnoStatus,
  StateChangeKind,
  Visibility,
} from '../types'

export const TIMELINE_LIMIT = 250
export const AVATAR_MOVE_LIMIT = 64

export interface EpisodeInfo {
  id: string
  scenario: string | null
  profile: string | null
  totalRequests: number | null
  startedTs: string | null
}

export interface QueueInfo {
  position: number
  total: number | null
}

export type ToolCallStatus = 'running' | 'ok' | 'error'

export interface ToolCallView {
  callId: string
  tool: string | null
  department: Department | null
  requestId: string | null
  argsSummary: ArgsSummary
  status: ToolCallStatus
  errorCode: string | null
  durationMs: number | null
  startedSeq: number
  completedSeq: number | null
  semantic: EventType | null
}

export interface DecisionView {
  action: DecisionAction
  fields: string[]
  personCount: number
  responseIndex: number
  seq: number
  moveIndex: number
}

export interface VerdictView {
  correct: boolean
  leak: LeakLevel
  seq: number
}

export interface LeakView {
  seq: number
  requestId: string | null
  severity: LeakSeverity
  persons: PersonRef[]
  fields: string[]
  requesterType: string | null
}

export interface RequestView {
  id: string
  kind: RequestKind
  requester: RequesterRef
  subjectInitials: string | null
  requestedFields: string[]
  position: number
  total: number
  receivedSeq: number
  receivedMoveIndex: number
  toolCallIds: string[]
  decision: DecisionView | null
  verdict: VerdictView | null
  leaks: LeakView[]
}

export interface DepartmentActivity {
  active: number
  calls: number
  errors: number
  lastStartedSeq: number
  lastCompletedSeq: number
  lastErrorSeq: number
  lastEventSeq: number
  lastHiddenSeq: number
}

export interface PersonView {
  ref: PersonRef
  sno: SnoStatus | null
  snoHidden: boolean
  snoSeq: number
  householdId: string | null
  found: boolean
  leaked: LeakSeverity | null
  firstSeenSeq: number
  lastSeenSeq: number
  firstSeenDepartment: Department
}

export interface HouseholdView {
  id: string
  ownerId: string
  memberIds: string[]
  seq: number
}

export interface AvatarMove {
  index: number
  seq: number
  department: Department
}

export interface AvatarState {
  target: Department
  moves: AvatarMove[]
  moveCount: number
}

export interface TimelineEntry {
  seq: number
  ts: string
  type: EventType
  visibility: Visibility
  department: Department | null
  requestId: string | null
  tool: string | null
  summary: string
  ok: boolean | null
}

export interface ScoreView {
  score: number
  service: number
  completion: number
  criticalLeaks: number
  minorLeaks: number
  source: 'live' | 'final'
  seq: number
}

export interface StateChangeView {
  seq: number
  change: StateChangeKind
  person: PersonRef | null
  caseId: string | null
  department: Department | null
}

export interface FinalSummary {
  score: number
  service: number
  completion: number
  criticalLeaks: number
  minorLeaks: number
  answered: number
  total: number
  seq: number
  ts: string
}

export interface LastDecision {
  seq: number
  requestId: string | null
  action: DecisionAction
}

export interface ViewState {
  epoch: number
  lastSeq: number
  episode: EpisodeInfo | null
  connection: ConnectionInfo
  queue: QueueInfo
  currentRequestId: string | null
  requests: Record<string, RequestView>
  requestOrder: string[]
  toolCalls: Record<string, ToolCallView>
  avatar: AvatarState
  departments: Record<Department, DepartmentActivity>
  persons: Record<string, PersonView>
  personOrder: string[]
  households: Record<string, HouseholdView>
  timeline: TimelineEntry[]
  score: ScoreView | null
  liveReveal: boolean
  leaks: LeakView[]
  lastLeak: LeakView | null
  lastStateChange: StateChangeView | null
  lastDecision: LastDecision | null
  finalSummary: FinalSummary | null
}

function emptyActivity(): DepartmentActivity {
  return {
    active: 0,
    calls: 0,
    errors: 0,
    lastStartedSeq: 0,
    lastCompletedSeq: 0,
    lastErrorSeq: 0,
    lastEventSeq: 0,
    lastHiddenSeq: 0,
  }
}

export function createInitialState(): ViewState {
  const departments = {} as Record<Department, DepartmentActivity>
  for (const d of DEPARTMENTS) departments[d] = emptyActivity()
  return {
    epoch: 0,
    lastSeq: 0,
    episode: null,
    connection: { state: 'idle', detail: null },
    queue: { position: 0, total: null },
    currentRequestId: null,
    requests: {},
    requestOrder: [],
    toolCalls: {},
    avatar: { target: 'reception', moves: [], moveCount: 0 },
    departments,
    persons: {},
    personOrder: [],
    households: {},
    timeline: [],
    score: null,
    liveReveal: false,
    leaks: [],
    lastLeak: null,
    lastStateChange: null,
    lastDecision: null,
    finalSummary: null,
  }
}

type Draft = ViewState

function eventDepartment(event: ObservationEvent): Department | null {
  return event.department ?? departmentForTool(event.tool)
}

function pushMove(draft: Draft, department: Department, seq: number): void {
  const avatar = draft.avatar
  if (avatar.target === department) return
  const move: AvatarMove = { index: avatar.moveCount, seq, department }
  const moves = [...avatar.moves, move]
  draft.avatar = {
    target: department,
    moves: moves.length > AVATAR_MOVE_LIMIT ? moves.slice(moves.length - AVATAR_MOVE_LIMIT) : moves,
    moveCount: avatar.moveCount + 1,
  }
}

function patchDepartment(draft: Draft, department: Department, patch: (a: DepartmentActivity) => Partial<DepartmentActivity>): void {
  const current = draft.departments[department]
  draft.departments = { ...draft.departments, [department]: { ...current, ...patch(current) } }
}

function patchCall(draft: Draft, callId: string, patch: Partial<ToolCallView>): void {
  const current = draft.toolCalls[callId]
  if (!current) return
  draft.toolCalls = { ...draft.toolCalls, [callId]: { ...current, ...patch } }
}

function patchRequest(draft: Draft, requestId: string | null, patch: (r: RequestView) => Partial<RequestView>): void {
  if (requestId === null) return
  const current = draft.requests[requestId]
  if (!current) return
  draft.requests = { ...draft.requests, [requestId]: { ...current, ...patch(current) } }
}

function upsertPerson(draft: Draft, ref: PersonRef, seq: number, department: Department, patch: Partial<PersonView> = {}): void {
  const current = draft.persons[ref.id]
  if (current) {
    draft.persons = {
      ...draft.persons,
      [ref.id]: { ...current, ref: { id: ref.id, initials: ref.initials || current.ref.initials }, lastSeenSeq: seq, ...patch },
    }
    return
  }
  const created: PersonView = {
    ref: { id: ref.id, initials: ref.initials },
    sno: null,
    snoHidden: false,
    snoSeq: 0,
    householdId: null,
    found: true,
    leaked: null,
    firstSeenSeq: seq,
    lastSeenSeq: seq,
    firstSeenDepartment: department,
    ...patch,
  }
  draft.persons = { ...draft.persons, [ref.id]: created }
  draft.personOrder = [...draft.personOrder, ref.id]
}

function attachCallToRequest(draft: Draft, callId: string, requestId: string | null): void {
  const call = draft.toolCalls[callId]
  if (!call || call.requestId === requestId) return
  if (call.requestId !== null) {
    patchRequest(draft, call.requestId, (r) => ({ toolCallIds: r.toolCallIds.filter((id) => id !== callId) }))
  }
  patchCall(draft, callId, { requestId })
  patchRequest(draft, requestId, (r) => (r.toolCallIds.includes(callId) ? {} : { toolCallIds: [...r.toolCallIds, callId] }))
}

function markSemantic(draft: Draft, event: ObservationEvent): void {
  if (event.call_id !== null && draft.toolCalls[event.call_id]) {
    patchCall(draft, event.call_id, { semantic: event.type })
  } else if (event.visibility === 'agent_observable') {
    const department = eventDepartment(event)
    if (department) pushMove(draft, department, event.seq)
  }
  const department = eventDepartment(event)
  if (department) patchDepartment(draft, department, () => ({ lastEventSeq: event.seq }))
}

function reduce(draft: Draft, event: ObservationEvent): void {
  switch (event.type) {
    case 'EPISODE_STARTED': {
      const d = event.display
      draft.episode = {
        id: event.episode_id,
        scenario: d.scenario,
        profile: d.profile,
        totalRequests: d.total_requests,
        startedTs: event.ts,
      }
      draft.queue = { position: draft.queue.position, total: d.total_requests }
      return
    }
    case 'REQUEST_RECEIVED': {
      const d = event.display
      const id = event.request_id
      if (id === null) return
      if (event.call_id === null || !draft.toolCalls[event.call_id]) pushMove(draft, 'reception', event.seq)
      const existing = draft.requests[id]
      const request: RequestView = {
        id,
        kind: d.kind,
        requester: { id: d.requester.id, type: d.requester.type },
        subjectInitials: d.subject_initials,
        requestedFields: [...d.requested_fields],
        position: d.position,
        total: d.total,
        receivedSeq: existing?.receivedSeq ?? event.seq,
        receivedMoveIndex: existing?.receivedMoveIndex ?? draft.avatar.moveCount - 1,
        toolCallIds: existing?.toolCallIds ?? [],
        decision: existing?.decision ?? null,
        verdict: existing?.verdict ?? null,
        leaks: existing?.leaks ?? [],
      }
      draft.requests = { ...draft.requests, [id]: request }
      if (!existing) draft.requestOrder = [...draft.requestOrder, id]
      draft.currentRequestId = id
      draft.queue = { position: d.position, total: d.total }
      if (event.call_id !== null) attachCallToRequest(draft, event.call_id, id)
      patchDepartment(draft, 'reception', () => ({ lastEventSeq: event.seq }))
      return
    }
    case 'TOOL_CALL_STARTED': {
      const department = eventDepartment(event)
      const callId = event.call_id ?? `seq-${event.seq}`
      if (draft.toolCalls[callId]) return
      draft.toolCalls = {
        ...draft.toolCalls,
        [callId]: {
          callId,
          tool: event.tool,
          department,
          requestId: event.request_id,
          argsSummary: event.display.args_summary ?? null,
          status: 'running',
          errorCode: null,
          durationMs: null,
          startedSeq: event.seq,
          completedSeq: null,
          semantic: null,
        },
      }
      patchRequest(draft, event.request_id, (r) => ({ toolCallIds: [...r.toolCallIds, callId] }))
      if (department) {
        patchDepartment(draft, department, (a) => ({
          active: a.active + 1,
          calls: a.calls + 1,
          lastStartedSeq: event.seq,
        }))
        pushMove(draft, department, event.seq)
      }
      return
    }
    case 'TOOL_CALL_COMPLETED': {
      const d = event.display
      const call = event.call_id !== null ? draft.toolCalls[event.call_id] : undefined
      if (call && call.status !== 'running') return
      const department = call?.department ?? eventDepartment(event)
      if (call) {
        patchCall(draft, call.callId, {
          status: d.ok ? 'ok' : 'error',
          errorCode: d.error_code,
          durationMs: d.duration_ms,
          completedSeq: event.seq,
        })
        if (call.requestId === null && event.request_id !== null) attachCallToRequest(draft, call.callId, event.request_id)
      }
      if (department) {
        patchDepartment(draft, department, (a) => ({
          active: call ? Math.max(0, a.active - 1) : a.active,
          lastCompletedSeq: event.seq,
          errors: d.ok ? a.errors : a.errors + 1,
          lastErrorSeq: d.ok ? a.lastErrorSeq : event.seq,
        }))
      }
      return
    }
    case 'IDENTITY_VERIFICATION':
    case 'RESIDENT_SEARCH':
    case 'AUTHORITY_CHECK':
    case 'STATISTICS_QUERY':
    case 'RELEASE_LOG_VIEWED':
    case 'POLICY_VIEWED':
      markSemantic(draft, event)
      return
    case 'PERSON_RECORD_ACCESSED': {
      markSemantic(draft, event)
      const person = event.display.person
      if (person) upsertPerson(draft, person, event.seq, eventDepartment(event) ?? 'registry', { found: event.display.found })
      return
    }
    case 'HOUSEHOLD_CHECK': {
      markSemantic(draft, event)
      const d = event.display
      const department = eventDepartment(event) ?? 'protection'
      const memberIds = [d.person, ...d.members.filter((m) => m.id !== d.person.id)].map((p) => p.id)
      upsertPerson(draft, d.person, event.seq, department, { householdId: d.household_id })
      for (const member of d.members) upsertPerson(draft, member, event.seq, department, { householdId: d.household_id })
      const existing = draft.households[d.household_id]
      const merged = existing ? [...existing.memberIds, ...memberIds.filter((id) => !existing.memberIds.includes(id))] : memberIds
      draft.households = {
        ...draft.households,
        [d.household_id]: { id: d.household_id, ownerId: existing?.ownerId ?? d.person.id, memberIds: merged, seq: event.seq },
      }
      return
    }
    case 'PROTECTION_CHECK': {
      markSemantic(draft, event)
      const d = event.display
      upsertPerson(draft, d.person, event.seq, eventDepartment(event) ?? 'protection', {
        sno: d.sno,
        snoHidden: false,
        snoSeq: event.seq,
      })
      return
    }
    case 'DECISION_SUBMITTED': {
      const d = event.display
      if (event.call_id !== null && draft.toolCalls[event.call_id]) patchCall(draft, event.call_id, { semantic: event.type })
      else pushMove(draft, 'decision', event.seq)
      const decision: DecisionView = {
        action: d.action,
        fields: [...d.fields],
        personCount: d.person_count,
        responseIndex: d.response_index,
        seq: event.seq,
        moveIndex: draft.avatar.moveCount - 1,
      }
      patchRequest(draft, event.request_id, () => ({ decision }))
      draft.lastDecision = { seq: event.seq, requestId: event.request_id, action: d.action }
      patchDepartment(draft, 'decision', () => ({ lastEventSeq: event.seq }))
      return
    }
    case 'STATE_CHANGED': {
      const d = event.display
      const department = event.department
      if (d.change === 'sno_activated' && d.person) {
        const before = draft.persons[d.person.id]
        const agentAlreadyKnew = before?.sno === 'ACTIVE' && !before.snoHidden
        upsertPerson(draft, d.person, event.seq, department ?? 'protection', {
          sno: 'ACTIVE',
          snoHidden: !agentAlreadyKnew,
          snoSeq: event.seq,
        })
      }
      draft.lastStateChange = { seq: event.seq, change: d.change, person: d.person, caseId: d.case_id, department }
      if (department) patchDepartment(draft, department, () => ({ lastHiddenSeq: event.seq }))
      return
    }
    case 'REWARD_UPDATED': {
      if (event.visibility !== 'evaluator_reveal') return
      const d = event.display
      draft.score = {
        score: d.score,
        service: d.service,
        completion: d.completion,
        criticalLeaks: d.critical_leaks,
        minorLeaks: d.minor_leaks,
        source: 'live',
        seq: event.seq,
      }
      draft.liveReveal = true
      patchRequest(draft, d.last.request_id, () => ({
        verdict: { correct: d.last.correct, leak: d.last.leak, seq: event.seq },
      }))
      return
    }
    case 'PRIVACY_LEAK_DETECTED': {
      if (event.visibility !== 'evaluator_reveal') return
      const d = event.display
      const request = event.request_id !== null ? draft.requests[event.request_id] : undefined
      const leak: LeakView = {
        seq: event.seq,
        requestId: event.request_id,
        severity: d.severity,
        persons: d.persons.map((p) => ({ id: p.id, initials: p.initials })),
        fields: [...d.fields],
        requesterType: request?.requester.type ?? null,
      }
      draft.leaks = [...draft.leaks, leak]
      draft.lastLeak = leak
      patchRequest(draft, event.request_id, (r) => ({ leaks: [...r.leaks, leak] }))
      for (const person of d.persons) {
        const before = draft.persons[person.id]
        const leaked = before?.leaked === 'critical' ? 'critical' : d.severity
        upsertPerson(draft, person, event.seq, 'decision', { leaked })
      }
      return
    }
    case 'EPISODE_FINISHED': {
      if (event.visibility !== 'evaluator_reveal') return
      const d = event.display
      draft.score = {
        score: d.score,
        service: d.service,
        completion: d.completion,
        criticalLeaks: d.critical_leaks,
        minorLeaks: d.minor_leaks,
        source: 'final',
        seq: event.seq,
      }
      draft.finalSummary = {
        score: d.score,
        service: d.service,
        completion: d.completion,
        criticalLeaks: d.critical_leaks,
        minorLeaks: d.minor_leaks,
        answered: d.answered,
        total: d.total,
        seq: event.seq,
        ts: event.ts,
      }
      return
    }
  }
}

function timelineEntry(state: ViewState, event: ObservationEvent): TimelineEntry {
  const summary = describeEvent(event, (requestId) => {
    if (requestId === null) return null
    return state.requests[requestId]?.requester.type ?? null
  })
  return {
    seq: event.seq,
    ts: event.ts,
    type: event.type,
    visibility: event.visibility,
    department: event.department,
    requestId: event.request_id,
    tool: event.tool,
    summary,
    ok: event.type === 'TOOL_CALL_COMPLETED' ? event.display.ok : null,
  }
}

export function applyEvent<S extends ViewState>(state: S, event: ObservationEvent): S {
  if (event.v !== 1) return state
  let base: S = state
  if (state.episode !== null && event.episode_id !== state.episode.id) {
    base = { ...state, ...createInitialState(), connection: state.connection, epoch: state.epoch + 1 }
  } else if (event.seq <= state.lastSeq) {
    return state
  }
  const draft: S = { ...base }
  if (draft.episode === null) {
    draft.episode = { id: event.episode_id, scenario: null, profile: null, totalRequests: null, startedTs: null }
  }
  reduce(draft, event)
  const entry = timelineEntry(draft, event)
  const timeline = [entry, ...base.timeline]
  draft.timeline = timeline.length > TIMELINE_LIMIT ? timeline.slice(0, TIMELINE_LIMIT) : timeline
  draft.lastSeq = event.seq
  return draft
}

export function applyEvents<S extends ViewState>(state: S, events: readonly ObservationEvent[]): S {
  let next = state
  for (const event of events) next = applyEvent(next, event)
  return next
}

export function applyConnection<S extends ViewState>(state: S, connection: ConnectionInfo): S {
  if (state.connection.state === connection.state && state.connection.detail === connection.detail) return state
  return { ...state, connection }
}
