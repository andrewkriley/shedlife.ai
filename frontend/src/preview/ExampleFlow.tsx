import { useState } from 'react'
import { ExampleLogin, ExampleSetup } from './ExampleGates'
import { ExampleJourney } from './ExampleJourney'
import { emptyJourney, type JourneyState } from './exampleData'

type Stage = 'setup' | 'login' | 'journey'

export function ExampleFlow() {
  const [stage, setStage] = useState<Stage>('setup')
  const [username, setUsername] = useState('admin')
  const [journey, setJourney] = useState<JourneyState>(emptyJourney)

  function restart() {
    setStage('setup')
    setUsername('admin')
    setJourney(emptyJourney())
  }

  return (
    <div className="preview-root">
      <aside className="preview-banner" role="note">
        <span>UI-only preview — no API calls. Functional wiring comes later.</span>
        <button type="button" className="button-secondary" onClick={restart}>
          Restart preview
        </button>
      </aside>
      <div className="preview-body">
        {stage === 'setup' ? (
          <div className="app-frame">
            <div className="app-frame__main">
              <ExampleSetup
                onComplete={(nextUsername) => {
                  setUsername(nextUsername)
                  setStage('login')
                }}
              />
            </div>
          </div>
        ) : null}
        {stage === 'login' ? (
          <div className="app-frame">
            <div className="app-frame__main">
              <ExampleLogin expectedUsername={username} onLoggedIn={() => setStage('journey')} />
            </div>
          </div>
        ) : null}
        {stage === 'journey' ? <ExampleJourney state={journey} onChange={setJourney} /> : null}
      </div>
    </div>
  )
}
