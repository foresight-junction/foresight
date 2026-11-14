import { useFrame } from '@react-three/fiber'
import { useRef, type RefObject } from 'react'
import { useSpectatorStore } from '../state/store'
import type { Department } from '../types'

export interface PulseState {
  activity: number
  kick: number
  error: number
  event: number
  hidden: number
  starts: number
  events: number
}

interface SeenSeqs {
  started: number
  error: number
  event: number
  hidden: number
}

function readSeqs(department: Department): SeenSeqs {
  const a = useSpectatorStore.getState().departments[department]
  return { started: a.lastStartedSeq, error: a.lastErrorSeq, event: a.lastEventSeq, hidden: a.lastHiddenSeq }
}

function decay(value: number, dt: number, rate: number): number {
  return Math.max(0, value - dt * rate)
}

export function useDepartmentPulse(department: Department): RefObject<PulseState> {
  const pulse = useRef<PulseState>({ activity: 0, kick: 0, error: 0, event: 0, hidden: 0, starts: 0, events: 0 })
  const seen = useRef<SeenSeqs | null>(null)

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.1)
    const a = useSpectatorStore.getState().departments[department]
    const p = pulse.current
    if (seen.current === null) seen.current = readSeqs(department)
    const s = seen.current
    if (a.lastStartedSeq !== s.started) {
      if (a.lastStartedSeq > s.started) {
        p.kick = 1
        p.starts += 1
      }
      s.started = a.lastStartedSeq
    }
    if (a.lastErrorSeq !== s.error) {
      if (a.lastErrorSeq > s.error) p.error = 1
      s.error = a.lastErrorSeq
    }
    if (a.lastEventSeq !== s.event) {
      if (a.lastEventSeq > s.event) {
        p.event = 1
        p.events += 1
      }
      s.event = a.lastEventSeq
    }
    if (a.lastHiddenSeq !== s.hidden) {
      if (a.lastHiddenSeq > s.hidden) p.hidden = 1
      s.hidden = a.lastHiddenSeq
    }
    const target = a.active > 0 ? 1 : 0
    p.activity += (target - p.activity) * (1 - Math.exp(-dt * (target > p.activity ? 7 : 2.2)))
    p.kick = decay(p.kick, dt, 1.3)
    p.error = decay(p.error, dt, 0.9)
    p.event = decay(p.event, dt, 1.1)
    p.hidden = decay(p.hidden, dt, 0.45)
  })

  return pulse
}
