import { useCallback, useEffect, useState } from 'react'
import { loadReplay } from '../api'
import { useSpectatorStore } from '../state/store'
import type { ObservationEvent } from '../types'

export const REPLAY_SPEEDS = [0.25, 0.5, 1, 2, 4, 8, 16] as const
const IDLE_CAP_MS = 2500
const FALLBACK_GAP_MS = 400
const BATCH_WINDOW_MS = 12

export type ReplayStatus = 'idle' | 'loading' | 'playing' | 'paused' | 'ended' | 'error'

export interface ReplayControls {
  status: ReplayStatus
  error: string | null
  path: string | null
  cursor: number
  total: number
  speed: number
  skipIdle: boolean
  play: () => void
  pause: () => void
  restart: () => void
  setSpeed: (speed: number) => void
  setSkipIdle: (skip: boolean) => void
}

function recordedGap(a: ObservationEvent, b: ObservationEvent): number | null {
  const gap = Date.parse(b.ts) - Date.parse(a.ts)
  return Number.isFinite(gap) ? Math.max(0, gap) : null
}

function playbackDelay(a: ObservationEvent, b: ObservationEvent, speed: number, skipIdle: boolean): number {
  const recorded = recordedGap(a, b) ?? FALLBACK_GAP_MS
  const gap = skipIdle ? Math.min(recorded, IDLE_CAP_MS) : recorded
  return gap / speed
}

export function useReplayFeed(path: string | null): ReplayControls {
  const [events, setEvents] = useState<ObservationEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(1)
  const [skipIdle, setSkipIdle] = useState(true)

  useEffect(() => {
    if (path === null) return
    const controller = new AbortController()
    const { setConnection } = useSpectatorStore.getState()
    setConnection({ state: 'connecting', detail: path })
    loadReplay(path, controller.signal)
      .then((loaded) => {
        setEvents(loaded)
        setConnection({ state: 'connected', detail: `replay · ${loaded.length} events` })
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        const message = reason instanceof Error ? reason.message : String(reason)
        setError(message)
        setConnection({ state: 'error', detail: message })
      })
    return () => controller.abort()
  }, [path])

  useEffect(() => {
    if (events === null || !playing || cursor >= events.length) return
    const delay = cursor === 0 ? 0 : playbackDelay(events[cursor - 1], events[cursor], speed, skipIdle)
    const timer = setTimeout(() => {
      let end = cursor + 1
      while (end < events.length && playbackDelay(events[end - 1], events[end], speed, skipIdle) < BATCH_WINDOW_MS) end++
      useSpectatorStore.getState().ingest(events.slice(cursor, end))
      setCursor(end)
    }, delay)
    return () => clearTimeout(timer)
  }, [events, playing, cursor, speed, skipIdle])

  const play = useCallback(() => setPlaying(true), [])
  const pause = useCallback(() => setPlaying(false), [])
  const restart = useCallback(() => {
    useSpectatorStore.getState().reset()
    setCursor(0)
    setPlaying(true)
  }, [])

  const total = events?.length ?? 0
  let status: ReplayStatus = 'idle'
  if (path !== null) {
    if (error !== null) status = 'error'
    else if (events === null) status = 'loading'
    else if (cursor >= total) status = 'ended'
    else status = playing ? 'playing' : 'paused'
  }

  return { status, error, path, cursor, total, speed, skipIdle, play, pause, restart, setSpeed, setSkipIdle }
}
