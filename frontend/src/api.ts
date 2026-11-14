import { EVENT_TYPES, VISIBILITIES } from './departments'
import type { ConnectionInfo, ObservationEvent } from './types'

const DEFAULT_BACKEND_URL = 'http://localhost:8000'
const RECONNECT_DELAY_MS = 3000

export const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || DEFAULT_BACKEND_URL).replace(/\/+$/, '')
const SPECTATOR_TOKEN = import.meta.env.VITE_SPECTATOR_TOKEN || ''

function endpoint(path: string, params: Record<string, string>): string {
  const query = new URLSearchParams({ token: SPECTATOR_TOKEN, ...params })
  return `${BACKEND_URL}${path}?${query.toString()}`
}

function isObservationEvent(value: unknown): value is ObservationEvent {
  if (value === null || typeof value !== 'object') return false
  const e = value as Record<string, unknown>
  return (
    e.v === 1 &&
    typeof e.seq === 'number' &&
    typeof e.ts === 'string' &&
    typeof e.episode_id === 'string' &&
    typeof e.type === 'string' &&
    (EVENT_TYPES as readonly string[]).includes(e.type) &&
    typeof e.visibility === 'string' &&
    (VISIBILITIES as readonly string[]).includes(e.visibility) &&
    e.display !== null &&
    typeof e.display === 'object'
  )
}

export function parseEvents(data: unknown): ObservationEvent[] {
  if (!Array.isArray(data)) throw new Error('Expected a JSON array of observation events')
  const events: ObservationEvent[] = []
  for (const item of data) {
    if (isObservationEvent(item)) events.push(item)
    else console.warn('Dropping malformed observation event', item)
  }
  return events.sort((a, b) => a.seq - b.seq)
}

export async function fetchHistory(afterSeq: number, signal?: AbortSignal): Promise<ObservationEvent[]> {
  const response = await fetch(endpoint('/observe/history', { after_seq: String(afterSeq) }), { signal })
  if (!response.ok) throw new Error(`History request failed with HTTP ${response.status}`)
  return parseEvents(await response.json())
}

export type EventSink = (events: ObservationEvent[]) => void
export type StatusSink = (status: ConnectionInfo) => void

export interface StreamCursor {
  episodeId: string | null
  lastSeq: number
}

export function openStream(onEvent: EventSink, onStatus: StatusSink, cursor: StreamCursor = { episodeId: null, lastSeq: 0 }): () => void {
  let episodeId = cursor.episodeId
  let lastSeq = cursor.lastSeq
  let source: EventSource | null = null
  let closed = false
  let catchingUp = false
  let catchUpAgain = false
  let buffer: ObservationEvent[] = []
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  const abort = new AbortController()

  const deliver = (events: ObservationEvent[]) => {
    const fresh: ObservationEvent[] = []
    for (const event of [...events].sort((a, b) => a.seq - b.seq)) {
      if (episodeId !== event.episode_id) {
        if (episodeId !== null && event.type !== 'EPISODE_STARTED' && event.seq !== 1) continue
        episodeId = event.episode_id
        lastSeq = 0
      }
      if (event.seq <= lastSeq) continue
      lastSeq = event.seq
      fresh.push(event)
    }
    if (fresh.length > 0) onEvent(fresh)
  }

  const catchUp = async () => {
    if (closed) return
    if (catchingUp) {
      catchUpAgain = true
      return
    }
    catchingUp = true
    try {
      deliver(await fetchHistory(lastSeq, abort.signal))
    } catch (error) {
      if (!closed) console.error('Observation history catch-up failed', error)
    } finally {
      catchingUp = false
      const pending = buffer
      buffer = []
      if (!closed) deliver(pending)
      if (catchUpAgain && !closed) {
        catchUpAgain = false
        void catchUp()
      }
    }
  }

  const connect = () => {
    if (closed) return
    onStatus({ state: source === null ? 'connecting' : 'reconnecting', detail: BACKEND_URL })
    const es = new EventSource(endpoint('/observe/stream', {}))
    source = es
    es.addEventListener('open', () => {
      onStatus({ state: 'connected', detail: BACKEND_URL })
      void catchUp()
    })
    es.addEventListener('observation', (message: MessageEvent<string>) => {
      let parsed: unknown
      try {
        parsed = JSON.parse(message.data)
      } catch (error) {
        console.warn('Dropping unparsable observation message', error)
        return
      }
      if (!isObservationEvent(parsed)) {
        console.warn('Dropping malformed observation event', parsed)
        return
      }
      const sameEpisode = parsed.episode_id === episodeId
      if (catchingUp || (sameEpisode && parsed.seq > lastSeq + 1)) {
        buffer.push(parsed)
        void catchUp()
        return
      }
      deliver([parsed])
    })
    es.addEventListener('error', () => {
      if (closed) return
      if (es.readyState === EventSource.CLOSED) {
        onStatus({ state: 'disconnected', detail: `Stream closed; retrying in ${RECONNECT_DELAY_MS / 1000}s` })
        es.close()
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS)
      } else {
        onStatus({ state: 'reconnecting', detail: BACKEND_URL })
      }
    })
  }

  connect()

  return () => {
    closed = true
    abort.abort()
    if (reconnectTimer !== null) clearTimeout(reconnectTimer)
    source?.close()
  }
}

export async function loadReplay(path: string, signal?: AbortSignal): Promise<ObservationEvent[]> {
  const base = new URL(import.meta.env.BASE_URL, window.location.origin)
  const url = new URL(path.replace(/^\/+/, ''), base)
  if (url.origin !== window.location.origin) throw new Error('Replay files must be served from this site (place them under public/)')
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(`Could not load replay ${url.pathname} (HTTP ${response.status})`)
  return parseEvents(await response.json())
}
