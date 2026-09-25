import { useState } from 'react'
import { ExampleLogin, ExampleSetup } from './ExampleGates'
import { ExampleOnboarding } from './ExampleOnboarding'
import { ExampleWorkspace } from './ExampleWorkspace'
import { SEEDED_ISSUE, emptyFoundations, type PreviewFoundations, type PreviewIssue } from './exampleData'

type Stage = 'setup' | 'login' | 'workspace'
type WorkspaceView = 'chat' | 'settings' | 'onboarding'

export function ExampleFlow() {
  const [stage, setStage] = useState<Stage>('setup')
  const [view, setView] = useState<WorkspaceView>('onboarding')
  const [username, setUsername] = useState('admin')
  const [foundations, setFoundations] = useState<PreviewFoundations>(emptyFoundations)
  const [issues, setIssues] = useState<PreviewIssue[]>([SEEDED_ISSUE])

  function restart() {
    setStage('setup')
    setView('onboarding')
    setUsername('admin')
    setFoundations(emptyFoundations())
    setIssues([SEEDED_ISSUE])
  }

  return (
    <div className="preview-root">
      <aside className="preview-banner" role="note">
        <span>
          UI-only preview — no API calls. Functional wiring comes later.
        </span>
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
              <ExampleLogin expectedUsername={username} onLoggedIn={() => setStage('workspace')} />
            </div>
          </div>
        ) : null}
        {stage === 'workspace' ? (
          <ExampleWorkspace
            view={view}
            setView={setView}
            foundations={foundations}
            onFoundationsChange={setFoundations}
            issues={issues}
            onIssuesChange={setIssues}
            onboarding={
              <ExampleOnboarding
                foundations={foundations}
                onChange={setFoundations}
                onFinished={() => setView('chat')}
              />
            }
          />
        ) : null}
      </div>
    </div>
  )
}
