import type { EventType } from '../../types'

type Glyph =
  | 'flag'
  | 'inbox'
  | 'play'
  | 'check'
  | 'id'
  | 'user'
  | 'search'
  | 'home'
  | 'shield'
  | 'badge'
  | 'chart'
  | 'list'
  | 'book'
  | 'stamp'
  | 'zap'
  | 'star'
  | 'alert'
  | 'finish'

const GLYPH: Record<EventType, Glyph> = {
  EPISODE_STARTED: 'flag',
  REQUEST_RECEIVED: 'inbox',
  TOOL_CALL_STARTED: 'play',
  TOOL_CALL_COMPLETED: 'check',
  IDENTITY_VERIFICATION: 'id',
  PERSON_RECORD_ACCESSED: 'user',
  RESIDENT_SEARCH: 'search',
  HOUSEHOLD_CHECK: 'home',
  PROTECTION_CHECK: 'shield',
  AUTHORITY_CHECK: 'badge',
  STATISTICS_QUERY: 'chart',
  RELEASE_LOG_VIEWED: 'list',
  POLICY_VIEWED: 'book',
  DECISION_SUBMITTED: 'stamp',
  STATE_CHANGED: 'zap',
  REWARD_UPDATED: 'star',
  PRIVACY_LEAK_DETECTED: 'alert',
  EPISODE_FINISHED: 'finish',
}

function paths(glyph: Glyph) {
  switch (glyph) {
    case 'flag':
      return <path d="M5 21V4m0 0h11l-2 4 2 4H5" />
    case 'inbox':
      return <path d="M3 13h5l1.5 3h5L16 13h5M5 5h14l2 8v6H3v-6z" />
    case 'play':
      return <path d="M8 5l11 7-11 7z" />
    case 'check':
      return <path d="M5 12.5l4.5 4.5L19 7.5" />
    case 'id':
      return <path d="M3 6h18v12H3zM7 10h4M7 14h6M15.5 11a1.5 1.5 0 1 0 0 .1" />
    case 'user':
      return <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c1-4 4.5-6 8-6s7 2 8 6" />
    case 'search':
      return <path d="M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM15.5 15.5L21 21" />
    case 'home':
      return <path d="M3 11l9-7 9 7M6 9.5V20h12V9.5" />
    case 'shield':
      return <path d="M12 3l8 3v6c0 4.5-3.5 7.8-8 9-4.5-1.2-8-4.5-8-9V6z" />
    case 'badge':
      return <path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.4 6.8 19.1l1-5.8L3.5 9.2l5.9-.9z" />
    case 'chart':
      return <path d="M4 20h16M7 16v-5M12 16V6M17 16v-8" />
    case 'list':
      return <path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" />
    case 'book':
      return <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 19V5" />
    case 'stamp':
      return <path d="M9 3h6l-1 7h4v4H6v-4h4zM5 18h14v3H5z" />
    case 'zap':
      return <path d="M13 2L4 14h7l-1 8 9-12h-7z" />
    case 'star':
      return <path d="M12 4v16M4 12h16M6.5 6.5l11 11M17.5 6.5l-11 11" />
    case 'alert':
      return <path d="M12 3l10 18H2zM12 10v5M12 18h.01" />
    case 'finish':
      return <path d="M5 21V4h14l-3 4.5L19 13H5" />
  }
}

export function EventIcon({ type }: { type: EventType }) {
  return (
    <svg
      className="event-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths(GLYPH[type])}
    </svg>
  )
}
