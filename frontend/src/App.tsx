import { Hud } from './components/Hud'
import { SpectatorScene } from './components/SpectatorScene'
import { useLiveFeed } from './hooks/useLiveFeed'
import { useReplayFeed } from './hooks/useReplayFeed'
import type { FeedMode } from './types'

const replayPath = new URLSearchParams(window.location.search).get('replay')
const mode: FeedMode = replayPath ? 'replay' : 'live'

export default function App() {
  useLiveFeed(mode === 'live')
  const replay = useReplayFeed(replayPath)
  return (
    <div className="app">
      <SpectatorScene />
      <Hud mode={mode} replay={replay} />
    </div>
  )
}
