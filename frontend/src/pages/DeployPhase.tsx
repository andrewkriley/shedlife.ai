import { useState } from 'react'
import { itemsForPhase, rowDetail, type JourneyState } from '../preview/exampleData'

const DEPLOY = itemsForPhase('deploy')

function emptyDeploy(): JourneyState {
  return Object.fromEntries(DEPLOY.map((item) => [item.id, { values: {}, done: false }]))
}

export function DeployPhase({
  onBack,
  onFinished,
}: {
  onBack: () => void
  onFinished: () => void
}) {
  const [step, setStep] = useState(0)
  const [state, setState] = useState<JourneyState>(emptyDeploy)
  const reviewing = step >= DEPLOY.length
  const item = reviewing ? null : DEPLOY[step]
  const done = DEPLOY.filter((entry) => state[entry.id]?.done).length

  return (
    <section className="journey chat-pane" aria-label="Deploy">
      <p className="journey-kicker">Deploy</p>
      {reviewing ? (
        <>
          <h1 className="journey__title">Ready</h1>
          <p className="journey__lede">{`${done} of ${DEPLOY.length} platforms are marked. Playbooks are not in MVP yet.`}</p>
          <div className="journey-list" aria-label="Deploy review">
            {DEPLOY.map((entry, index) => (
              <button
                key={entry.id}
                type="button"
                className="review-row"
                onClick={() => setStep(index)}
              >
                <span className="review-row__title">{entry.title}</span>
                <span className="review-row__value">{rowDetail(entry, state[entry.id])}</span>
              </button>
            ))}
          </div>
          <div className="journey-actions">
            <button type="button" onClick={onFinished}>
              Back to chat
            </button>
            <button type="button" className="button-secondary" onClick={onBack}>
              Back to Onboarding
            </button>
          </div>
        </>
      ) : item ? (
        <>
          <ol className="step-dots" aria-label="Deploy progress">
            {DEPLOY.map((entry, dot) => (
              <li
                key={entry.id}
                className={dot === step ? 'is-current' : dot < step ? 'is-done' : undefined}
              >
                <span className="visually-hidden">
                  {entry.title}
                  {dot === step ? ' (current)' : dot < step ? ' (done)' : ''}
                </span>
              </li>
            ))}
          </ol>
          <p className="journey-count">{`${step + 1} of ${DEPLOY.length}`}</p>
          <h1 className="journey__title">{item.title}</h1>
          <p className="journey__lede">{item.detail}</p>
          <p className="hint">Marked locally. Deploy playbooks are not wired yet.</p>
          <div className="journey-actions">
            <button
              type="button"
              onClick={() => {
                const next = {
                  ...state,
                  [item.id]: { values: state[item.id]?.values ?? {}, done: true },
                }
                setState(next)
                const restDone = DEPLOY.slice(step + 1).every((entry) => next[entry.id]?.done)
                setStep(restDone ? DEPLOY.length : step + 1)
              }}
            >
              {item.actionLabel ?? 'Continue'}
            </button>
            <button
              type="button"
              className="button-secondary"
              onClick={() => {
                if (step === 0) onBack()
                else setStep(step - 1)
              }}
            >
              Back
            </button>
          </div>
        </>
      ) : null}
    </section>
  )
}
