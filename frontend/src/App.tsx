import { useState } from 'react'
import { Chat } from './pages/Chat'
import { Login } from './pages/Login'
import { Settings } from './pages/Settings'

type View = 'chat' | 'settings'

function App() {
  const [loggedIn, setLoggedIn] = useState(false)
  const [view, setView] = useState<View>('chat')

  if (!loggedIn) {
    return <Login onLoggedIn={() => setLoggedIn(true)} />
  }
  return view === 'settings' ? (
    <Settings onClose={() => setView('chat')} />
  ) : (
    <Chat onOpenSettings={() => setView('settings')} />
  )
}

export default App
