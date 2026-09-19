import { useEffect, useState } from 'react'
import { getSetupStatus } from './lib/api'
import { Chat } from './pages/Chat'
import { FoundationsPanel } from './pages/FoundationsPanel'
import { IssuesPanel } from './pages/IssuesPanel'
import { Login } from './pages/Login'
import { Settings } from './pages/Settings'
import { Setup } from './pages/Setup'

type View = 'chat' | 'settings'

function App() {
  const [setupNeeded, setSetupNeeded] = useState<boolean | null>(null)
  const [loggedIn, setLoggedIn] = useState(false)
  const [view, setView] = useState<View>('chat')

  useEffect(() => {
    getSetupStatus()
      .then((status) => setSetupNeeded(status.needed))
      .catch(() => setSetupNeeded(false))
  }, [])

  if (setupNeeded === null) {
    return <p role="status">Loading…</p>
  }
  if (setupNeeded) {
    return (
      <Setup
        onComplete={() => {
          setSetupNeeded(false)
          setLoggedIn(true)
        }}
      />
    )
  }
  if (!loggedIn) {
    return <Login onLoggedIn={() => setLoggedIn(true)} />
  }
  if (view === 'settings') {
    return <Settings onClose={() => setView('chat')} />
  }
  return (
    <div className="app-shell">
      <Chat onOpenSettings={() => setView('settings')} />
      <aside className="sidebar">
        <FoundationsPanel />
        <IssuesPanel />
      </aside>
    </div>
  )
}

export default App
