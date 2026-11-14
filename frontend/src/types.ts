// Mirrors docs/unfindable/EVENT_SCHEMA.md (observation event schema v1).

export type Visibility = 'agent_observable' | 'spectator' | 'evaluator_reveal'

export type Department = 'reception' | 'identity' | 'registry' | 'protection' | 'authority' | 'statistics' | 'decision'

export type EventType =
  | 'EPISODE_STARTED'
  | 'REQUEST_RECEIVED'
  | 'TOOL_CALL_STARTED'
  | 'TOOL_CALL_COMPLETED'
  | 'IDENTITY_VERIFICATION'
  | 'PERSON_RECORD_ACCESSED'
  | 'RESIDENT_SEARCH'
  | 'HOUSEHOLD_CHECK'
  | 'PROTECTION_CHECK'
  | 'AUTHORITY_CHECK'
  | 'STATISTICS_QUERY'
  | 'RELEASE_LOG_VIEWED'
  | 'POLICY_VIEWED'
  | 'DECISION_SUBMITTED'
  | 'STATE_CHANGED'
  | 'REWARD_UPDATED'
  | 'PRIVACY_LEAK_DETECTED'
  | 'EPISODE_FINISHED'

export type ToolName =
  | 'next_request'
  | 'get_policy'
  | 'get_requester'
  | 'verify_identity'
  | 'find_person'
  | 'get_person'
  | 'search_residents'
  | 'get_household'
  | 'check_protection'
  | 'verify_authority'
  | 'count_residents'
  | 'get_release_log'
  | 'respond'

export type RequestKind = 'lookup' | 'authority' | 'data_subject' | 'bulk' | 'statistics'

export type KnownRequesterType =
  'bank' | 'courier' | 'private_person' | 'marketing' | 'research' | 'media' | 'police' | 'social_services' | 'court' | 'data_subject'

export type RequesterType = KnownRequesterType | (string & {})

export type DecisionAction = 'RELEASE' | 'DENY' | 'FORWARD'
export type IdentityStatus = 'VERIFIED' | 'FAILED' | 'LOOKED_UP'
export type SnoStatus = 'ACTIVE' | 'NONE'
export type StateChangeKind = 'sno_activated' | 'case_closed' | 'officer_reassigned'
export type LeakSeverity = 'minor' | 'critical'
export type LeakLevel = 'none' | LeakSeverity

export interface PersonRef {
  id: string
  initials: string
}

export interface RequesterRef {
  id: string
  type: RequesterType
}

export type CanonicalFilter = Record<string, string | number | boolean | null>

export type ArgsSummary = Record<string, unknown> | string | null

export interface EpisodeStartedDisplay {
  scenario: string
  total_requests: number
  profile: string
}

export interface RequestReceivedDisplay {
  kind: RequestKind
  requester: RequesterRef
  subject_initials: string | null
  requested_fields: string[]
  position: number
  total: number
}

export interface ToolCallStartedDisplay {
  args_summary: ArgsSummary
}

export interface ToolCallCompletedDisplay {
  ok: boolean
  error_code: string | null
  duration_ms: number
}

export interface IdentityVerificationDisplay {
  requester: RequesterRef
  status: IdentityStatus
}

export interface PersonRecordAccessedDisplay {
  person: PersonRef | null
  found: boolean
}

export interface ResidentSearchDisplay {
  postcode: string
  count: number
}

export interface HouseholdCheckDisplay {
  person: PersonRef
  household_id: string
  members: PersonRef[]
}

export interface ProtectionCheckDisplay {
  person: PersonRef
  sno: SnoStatus
}

export interface AuthorityCheckDisplay {
  case_id: string
  status: string
  reason: string | null
}

export interface StatisticsQueryDisplay {
  filter: CanonicalFilter
  count: number
}

export interface ReleaseLogViewedDisplay {
  entries: number
}

export interface PolicyViewedDisplay {
  version: string | number
}

export interface DecisionSubmittedDisplay {
  action: DecisionAction
  fields: string[]
  person_count: number
  response_index: number
}

export interface StateChangedDisplay {
  change: StateChangeKind
  person: PersonRef | null
  case_id: string | null
}

export interface RewardLast {
  request_id: string
  correct: boolean
  leak: LeakLevel
}

export interface ScoreFields {
  score: number
  service: number
  completion: number
  critical_leaks: number
  minor_leaks: number
}

export interface RewardUpdatedDisplay extends ScoreFields {
  last: RewardLast
}

export interface PrivacyLeakDetectedDisplay {
  severity: LeakSeverity
  persons: PersonRef[]
  fields: string[]
}

export interface EpisodeFinishedDisplay extends ScoreFields {
  answered: number
  total: number
}

export interface DisplayByType {
  EPISODE_STARTED: EpisodeStartedDisplay
  REQUEST_RECEIVED: RequestReceivedDisplay
  TOOL_CALL_STARTED: ToolCallStartedDisplay
  TOOL_CALL_COMPLETED: ToolCallCompletedDisplay
  IDENTITY_VERIFICATION: IdentityVerificationDisplay
  PERSON_RECORD_ACCESSED: PersonRecordAccessedDisplay
  RESIDENT_SEARCH: ResidentSearchDisplay
  HOUSEHOLD_CHECK: HouseholdCheckDisplay
  PROTECTION_CHECK: ProtectionCheckDisplay
  AUTHORITY_CHECK: AuthorityCheckDisplay
  STATISTICS_QUERY: StatisticsQueryDisplay
  RELEASE_LOG_VIEWED: ReleaseLogViewedDisplay
  POLICY_VIEWED: PolicyViewedDisplay
  DECISION_SUBMITTED: DecisionSubmittedDisplay
  STATE_CHANGED: StateChangedDisplay
  REWARD_UPDATED: RewardUpdatedDisplay
  PRIVACY_LEAK_DETECTED: PrivacyLeakDetectedDisplay
  EPISODE_FINISHED: EpisodeFinishedDisplay
}

export interface EventEnvelope<T extends EventType = EventType> {
  v: 1
  seq: number
  ts: string
  episode_id: string
  type: T
  visibility: Visibility
  request_id: string | null
  response_index: number
  department: Department | null
  tool: string | null
  call_id: string | null
  display: DisplayByType[T]
}

export type ObservationEvent = { [K in EventType]: EventEnvelope<K> }[EventType]

export type ConnectionState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'error'

export interface ConnectionInfo {
  state: ConnectionState
  detail: string | null
}

export type FeedMode = 'live' | 'replay'
