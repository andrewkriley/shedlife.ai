import { useEffect, useState } from 'react'
import { AssistantStatus } from './components/AssistantStatus'
import { DebugDock } from './components/DebugDock'
import { getSetupStatus } from './lib/api'
import { Chat } from './pages/Chat'
import { FoundationsPanel } from './pages/FoundationsPanel'
import { IssuesPanel } from './pages/IssuesPanel'
import { Login } from './pages/Login'
import { Settings } from './pages/Settings'
import { Setup } from './pages/Setup'

type View = 'chat' | 'settings'
type ReviewTab = 'foundations' | 'issues'

function App() {
  const [setupNeeded, setSetupNeeded] = useState<boolean | null>(null)
  const [hasOperator, setHasOperator] = useState(false)
  const [loggedIn, setLoggedIn] = useState(false)
  const [view, setView] = useState<View>('chat')
  const [reviewTab, setReviewTab] = useState<ReviewTab>('foundations')

  useEffect(() => {
    getSetupStatus()
      .then((status) => {
        setSetupNeeded(status.needed)
        setHasOperator(Boolean(status.has_operator))
      })
      .catch(() => setSetupNeeded(false))
  }, [])

  if (setupNeeded === null) {
    return (
      <>
        <p role="status">Loading…</p>
        <DebugDock />
      </>
    )
  }
  if (setupNeeded && !hasOperator) {
    return (
      <>
        <Setup
          onComplete={() => {
            setSetupNeeded(false)
            setHasOperator(true)
            setLoggedIn(true)
          }}
        />
        <DebugDock />
      </>
    )
  }
  if (!loggedIn) {
    return (
      <>
        <Login onLoggedIn={() => setLoggedIn(true)} />
        <DebugDock />
      </>
    )
  }
  if (setupNeeded) {
    return (
      <>
        <Setup
          hasOperator
          onComplete={() => {
            setSetupNeeded(false)
          }}
        />
        <DebugDock />
      </>
    )
  }

  return (
    <div className="app-shell" data-layout="single-window">
      <header className="app-header">
        <h1>The Shed</h1>
        <AssistantStatus />
        {view === 'settings' ? (
          <button type="button" className="button-secondary" onClick={() => setView('chat')}>
            Back to chat
          </button>
        ) : (
          <button type="button" className="button-secondary" onClick={() => setView('settings')}>
            Settings
          </button>
        )}
      </header>
      {view === 'settings' ? (
        <Settings onClose={() => setView('chat')} />
      ) : (
        <>
          <Chat />
          <aside className="sidebar">
            <div className="sidebar-tabs" role="tablist" aria-label="review">
              <button
                type="button"
                role="tab"
                aria-selected={reviewTab === 'foundations'}
                className={reviewTab === 'foundations' ? 'is-active' : undefined}
                onClick={() => setReviewTab('foundations')}
              >
                Foundations
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={reviewTab === 'issues'}
                className={reviewTab === 'issues' ? 'is-active' : undefined}
                onClick={() => setReviewTab('issues')}
              >
                Issues
              </button>
            </div>
            <div className="sidebar-panel" role="tabpanel">
              {reviewTab === 'foundations' ? <FoundationsPanel /> : <IssuesPanel />}
            </div>
          </aside>
        </>
      )}
      <DebugDock />
    </div>
  )
}

export default App
