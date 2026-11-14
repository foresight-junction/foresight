import { create } from 'zustand'
import type { ConnectionInfo, ObservationEvent } from '../types'
import { applyConnection, applyEvents, createInitialState, type ViewState } from './applyEvent'

export interface SpectatorStore extends ViewState {
  ingest: (events: readonly ObservationEvent[]) => void
  setConnection: (connection: ConnectionInfo) => void
  reset: () => void
}

export const useSpectatorStore = create<SpectatorStore>()((set) => ({
  ...createInitialState(),
  ingest: (events) => {
    if (events.length === 0) return
    set((state) => applyEvents(state, events))
  },
  setConnection: (connection) => set((state) => applyConnection(state, connection)),
  reset: () => set((state) => ({ ...createInitialState(), connection: state.connection, epoch: state.epoch + 1 })),
}))
