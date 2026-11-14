import type { ArgsSummary, CanonicalFilter, EventType, ObservationEvent, PersonRef } from './types'

export const EVENT_LABEL: Record<EventType, string> = {
  EPISODE_STARTED: 'Shift started',
  REQUEST_RECEIVED: 'Request received',
  TOOL_CALL_STARTED: 'Tool call',
  TOOL_CALL_COMPLETED: 'Tool result',
  IDENTITY_VERIFICATION: 'Identity check',
  PERSON_RECORD_ACCESSED: 'Record accessed',
  RESIDENT_SEARCH: 'Resident search',
  HOUSEHOLD_CHECK: 'Household check',
  PROTECTION_CHECK: 'Protection check',
  AUTHORITY_CHECK: 'Authority check',
  STATISTICS_QUERY: 'Statistics query',
  RELEASE_LOG_VIEWED: 'Release log',
  POLICY_VIEWED: 'Policy viewed',
  DECISION_SUBMITTED: 'Decision',
  STATE_CHANGED: 'State changed',
  REWARD_UPDATED: 'Verdict',
  PRIVACY_LEAK_DETECTED: 'Privacy leak',
  EPISODE_FINISHED: 'Shift finished',
}

export function humanize(value: string): string {
  return value.replace(/_/g, ' ')
}

export function formatPersons(persons: PersonRef[]): string {
  if (persons.length === 0) return 'no person'
  return persons.map((p) => p.initials).join(', ')
}

export function formatFields(fields: string[]): string {
  return fields.length === 0 ? 'no fields' : fields.join(', ')
}

export function formatFilter(filter: CanonicalFilter): string {
  const parts = Object.entries(filter).map(([k, v]) => `${k}=${String(v)}`)
  return parts.length === 0 ? '{}' : parts.join(' · ')
}

function formatArgValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(formatArgValue).join(', ')
  if (value !== null && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${k}=${formatArgValue(v)}`)
      .join(' ')
  }
  return String(value)
}

export function formatArgs(args: ArgsSummary): string {
  if (args === null || args === undefined) return ''
  if (typeof args === 'string') return args
  return Object.entries(args)
    .map(([k, v]) => `${k}=${formatArgValue(v)}`)
    .join(' ')
}

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toFixed(3)
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${Math.round(value * 100)}%`
}

export function formatClock(ts: string): string {
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return ts
  const pad = (n: number, w = 2) => String(n).padStart(w, '0')
  return `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}.${pad(date.getUTCMilliseconds(), 3)}`
}

export function leakSentence(severity: string, fields: string[], persons: PersonRef[], requesterType: string | null): string {
  const to = requesterType ? ` disclosed to ${requesterType}` : ' disclosed'
  return `${severity} leak: ${formatFields(fields)} of ${formatPersons(persons)}${to}`
}

export function describeEvent(event: ObservationEvent, requesterTypeOf: (requestId: string | null) => string | null): string {
  switch (event.type) {
    case 'EPISODE_STARTED':
      return `Shift started · ${event.display.scenario} · ${event.display.total_requests} requests`
    case 'REQUEST_RECEIVED': {
      const d = event.display
      const subject = d.subject_initials ? ` about ${d.subject_initials}` : ''
      return `${humanize(d.kind)} request from ${humanize(d.requester.type)}${subject}`
    }
    case 'TOOL_CALL_STARTED': {
      const args = formatArgs(event.display.args_summary)
      return `${event.tool ?? 'tool'}(${args})`
    }
    case 'TOOL_CALL_COMPLETED':
      return event.display.ok
        ? `${event.tool ?? 'tool'} ok · ${Math.round(event.display.duration_ms)} ms`
        : `${event.tool ?? 'tool'} failed · ${event.display.error_code ?? 'error'}`
    case 'IDENTITY_VERIFICATION':
      return `Requester ${event.display.requester.id} (${humanize(event.display.requester.type)}): ${event.display.status}`
    case 'PERSON_RECORD_ACCESSED':
      return event.display.found && event.display.person
        ? `Record ${event.display.person.id} (${event.display.person.initials}) opened`
        : 'No matching record'
    case 'RESIDENT_SEARCH':
      return `Resident search in ${event.display.postcode}: ${event.display.count} found`
    case 'HOUSEHOLD_CHECK':
      return `Household ${event.display.household_id} of ${event.display.person.initials}: ${event.display.members.length} members`
    case 'PROTECTION_CHECK':
      return `${event.display.person.initials} (${event.display.person.id}): SNO ${event.display.sno}`
    case 'AUTHORITY_CHECK': {
      const reason = event.display.reason ? ` (${humanize(event.display.reason)})` : ''
      return `Case ${event.display.case_id}: ${event.display.status}${reason}`
    }
    case 'STATISTICS_QUERY':
      return `Count ${formatFilter(event.display.filter)} → ${event.display.count}`
    case 'RELEASE_LOG_VIEWED':
      return `Release log viewed · ${event.display.entries} entries`
    case 'POLICY_VIEWED':
      return `Policy ${event.display.version} viewed`
    case 'DECISION_SUBMITTED': {
      const d = event.display
      const fields = d.fields.length > 0 ? ` · ${formatFields(d.fields)}` : ''
      const persons = d.person_count > 0 ? ` · ${d.person_count} person${d.person_count === 1 ? '' : 's'}` : ''
      return `${d.action}${fields}${persons}`
    }
    case 'STATE_CHANGED': {
      const d = event.display
      if (d.change === 'sno_activated') return `SNO issued${d.person ? ` for ${d.person.initials}` : ''}`
      if (d.change === 'case_closed') return d.case_id ? `Case ${d.case_id} closed` : 'Case closed'
      return `Officer reassigned${d.case_id ? ` on case ${d.case_id}` : ''}`
    }
    case 'REWARD_UPDATED': {
      const l = event.display.last
      const leak = l.leak === 'none' ? 'no leak' : `${l.leak} leak`
      return `${l.request_id}: ${l.correct ? 'correct' : 'incorrect'} · ${leak} · score ${formatScore(event.display.score)}`
    }
    case 'PRIVACY_LEAK_DETECTED':
      return leakSentence(event.display.severity, event.display.fields, event.display.persons, requesterTypeOf(event.request_id))
    case 'EPISODE_FINISHED':
      return `Shift finished · score ${formatScore(event.display.score)} · ${event.display.answered}/${event.display.total} answered`
  }
}
