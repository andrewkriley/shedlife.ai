import { useState } from 'react'
import { Chat } from './pages/Chat'
import { Login } from './pages/Login'

function App() {
  const [loggedIn, setLoggedIn] = useState(false)

  return loggedIn ? <Chat /> : <Login onLoggedIn={() => setLoggedIn(true)} />
}

export default App
