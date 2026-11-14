import type { Department, EventType, Visibility } from './types'

export const DEPARTMENTS: readonly Department[] = ['reception', 'identity', 'registry', 'statistics', 'decision', 'authority', 'protection']

export const EVENT_TYPES: readonly EventType[] = [
  'EPISODE_STARTED',
  'REQUEST_RECEIVED',
  'TOOL_CALL_STARTED',
  'TOOL_CALL_COMPLETED',
  'IDENTITY_VERIFICATION',
  'PERSON_RECORD_ACCESSED',
  'RESIDENT_SEARCH',
  'HOUSEHOLD_CHECK',
  'PROTECTION_CHECK',
  'AUTHORITY_CHECK',
  'STATISTICS_QUERY',
  'RELEASE_LOG_VIEWED',
  'POLICY_VIEWED',
  'DECISION_SUBMITTED',
  'STATE_CHANGED',
  'REWARD_UPDATED',
  'PRIVACY_LEAK_DETECTED',
  'EPISODE_FINISHED',
]

export const VISIBILITIES: readonly Visibility[] = ['agent_observable', 'spectator', 'evaluator_reveal']

export const DEPARTMENT_LABEL: Record<Department, string> = {
  reception: 'Reception',
  identity: 'Identity',
  registry: 'Registry',
  protection: 'Protection Office',
  authority: 'Authority Desk',
  statistics: 'Statistics',
  decision: 'Decision Room',
}

export const DEPARTMENT_COLOR: Record<Department, string> = {
  reception: '#3b82f6',
  identity: '#eab308',
  registry: '#14b8a6',
  protection: '#0ea5e9',
  authority: '#ec4899',
  statistics: '#6366f1',
  decision: '#475569',
}

export const PALETTE = {
  ink: '#0f172a',
  neutralStamp: '#94a3b8',
  correct: '#22c55e',
  incorrect: '#f59e0b',
  leak: '#ef4444',
  hidden: '#a855f7',
  floor: '#f8f9fb',
  ground: '#dce2eb',
  background: '#eef1f6',
} as const

const TOOL_DEPARTMENT: Record<string, Department> = {
  next_request: 'reception',
  get_policy: 'reception',
  get_requester: 'identity',
  verify_identity: 'identity',
  find_person: 'registry',
  get_person: 'registry',
  search_residents: 'registry',
  get_household: 'protection',
  check_protection: 'protection',
  verify_authority: 'authority',
  count_residents: 'statistics',
  get_release_log: 'statistics',
  respond: 'decision',
}

export function departmentForTool(tool: string | null): Department | null {
  if (tool === null) return null
  return TOOL_DEPARTMENT[tool] ?? null
}

export function isDepartment(value: unknown): value is Department {
  return typeof value === 'string' && (DEPARTMENTS as readonly string[]).includes(value)
}
