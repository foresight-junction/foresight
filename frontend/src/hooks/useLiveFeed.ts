import { useEffect } from 'react'
import { openStream } from '../api'
import { useSpectatorStore } from '../state/store'

export function useLiveFeed(enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return
    const { ingest, setConnection, episode, lastSeq } = useSpectatorStore.getState()
    return openStream(ingest, setConnection, { episodeId: episode?.id ?? null, lastSeq })
  }, [enabled])
}
