import { useState, type FormEvent } from 'react'
import {
  fieldsFilled,
  itemsForPhase,
  joinTitles,
  phaseProgress,
  prereqSummary,
  rowDetail,
  type ItemState,
  type JourneyItemDef,
  type JourneyState,
} from './exampleData'

const PREREQ = itemsForPhase('prereq')
const DEPLOY = itemsForPhase('deploy')

export function ExampleJourney({
  state,
  onChange,
}: {
  state: JourneyState
  onChange: (next: JourneyState) => void
}) {
  const [phase, setPhase] = useState<'prereq' | 'deploy'>('prereq')
  const [step, setStep] = useState(0)

  function saveItem(itemDef: JourneyItemDef, values: Record<string, string>): JourneyState {
    const next = {
      ...state,
      [itemDef.id]: { values, done: true },
    }
    onChange(next)
    return next
  }

  function markDone(itemDef: JourneyItemDef): JourneyState {
    const current = state[itemDef.id] ?? { values: {}, done: false }
    const next = {
      ...state,
      [itemDef.id]: { ...current, done: true },
    }
    onChange(next)
    return next
  }

  if (phase === 'deploy') {
    const reviewing = step >= DEPLOY.length
    const item = reviewing ? null : DEPLOY[step]
    return (
      <div className="journey-shell">
        <main className="journey" aria-label="Deploy">
          <p className="journey-kicker">Deploy</p>
          {reviewing ? (
            <DeployReview
              state={state}
              progress={phaseProgress('deploy', state)}
              onEdit={(index) => setStep(index)}
              onBack={() => {
                setPhase('prereq')
                setStep(PREREQ.length)
              }}
            />
          ) : item ? (
            <ActionStep
              key={item.id}
              item={item}
              items={DEPLOY}
              index={step}
              total={DEPLOY.length}
              progressLabel="Deploy progress"
              onContinue={() => {
                const next = markDone(item)
                const restDone = DEPLOY.slice(step + 1).every((entry) => next[entry.id]?.done)
                setStep(restDone ? DEPLOY.length : step + 1)
              }}
              onBack={
                step === 0
                  ? () => {
                      setPhase('prereq')
                      setStep(PREREQ.length)
                    }
                  : () => setStep(step - 1)
              }
            />
          ) : null}
        </main>
      </div>
    )
  }

  const progress = phaseProgress('prereq', state)
  const reviewing = step >= PREREQ.length
  const item = reviewing ? null : PREREQ[step]

  return (
    <div className="journey-shell">
      <main className="journey" aria-label="Pre-req">
        <p className="journey-kicker">Pre-req</p>
        {reviewing ? (
          <PrereqSummary
            state={state}
            progress={progress}
            onEdit={(index) => setStep(index)}
            onContinue={() => {
              setPhase('deploy')
              setStep(0)
            }}
          />
        ) : item ? (
          <PrereqStep
            key={item.id}
            item={item}
            current={state[item.id] ?? { values: {}, done: false }}
            index={step}
            total={PREREQ.length}
            onSave={(values) => {
              const next = saveItem(item, values)
              const restDone = PREREQ.slice(step + 1).every((entry) => next[entry.id]?.done)
              setStep(restDone ? PREREQ.length : step + 1)
            }}
            onBack={step === 0 ? undefined : () => setStep(step - 1)}
          />
        ) : null}
      </main>
    </div>
  )
}

function PrereqStep({
  item,
  current,
  index,
  total,
  onSave,
  onBack,
}: {
  item: JourneyItemDef
  current: ItemState
  index: number
  total: number
  onSave: (values: Record<string, string>) => void
  onBack?: () => void
}) {
  const [draft, setDraft] = useState(current.values)
  const [error, setError] = useState<string | null>(null)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    const values = filledValues(item, draft, current)
    if (!fieldsFilled(item, { values, done: false })) {
      const missing = item.fields.find((field) => !values[field.id]?.trim())
      setError(`${missing?.label ?? item.title} is required`)
      return
    }
    onSave(values)
  }

  return (
    <>
      <StepDots items={PREREQ} index={index} label="Pre-req progress" />
      <p className="journey-count">{`${index + 1} of ${total}`}</p>
      <h1 className="journey__title">{item.title}</h1>
      <p className="journey__lede">{item.detail}</p>
      <form className="journey-form" onSubmit={handleSubmit}>
        {item.fields.map((field) => {
          const id = `journey-${item.id}-${field.id}`
          return (
            <div key={field.id} className="journey-field">
              <label htmlFor={id}>{field.label}</label>
              {field.input === 'textarea' ? (
                <textarea
                  id={id}
                  value={draft[field.id] ?? ''}
                  placeholder={
                    current.done ? 'Saved. Paste a new key to replace it.' : field.placeholder
                  }
                  onChange={(e) => setDraft({ ...draft, [field.id]: e.target.value })}
                />
              ) : (
                <input
                  id={id}
                  type={field.input}
                  value={draft[field.id] ?? ''}
                  placeholder={
                    current.done && field.input === 'password'
                      ? 'Saved. Paste a new value to replace it.'
                      : field.placeholder
                  }
                  autoComplete="off"
                  onChange={(e) => setDraft({ ...draft, [field.id]: e.target.value })}
                />
              )}
            </div>
          )
        })}
        {error && <p role="alert">{error}</p>}
        <div className="journey-actions">
          <button type="submit">Continue</button>
          {onBack ? (
            <button type="button" className="button-secondary" onClick={onBack}>
              Back
            </button>
          ) : null}
        </div>
      </form>
    </>
  )
}

function PrereqSummary({
  state,
  progress,
  onEdit,
  onContinue,
}: {
  state: JourneyState
  progress: { done: number; total: number }
  onEdit: (index: number) => void
  onContinue: () => void
}) {
  return (
    <>
      <h1 className="journey__title">Ready</h1>
      <p className="journey__lede">{prereqSummary(state)}</p>
      <div className="journey-list" aria-label="Pre-req review">
        {PREREQ.map((item, index) => (
          <button
            key={item.id}
            type="button"
            className="review-row"
            onClick={() => onEdit(index)}
          >
            <span className="review-row__title">{item.title}</span>
            <span className="review-row__value">{rowDetail(item, state[item.id])}</span>
          </button>
        ))}
      </div>
      <section className="journey-next" aria-label="Next phase">
        <p className="journey-next__title">Deploy is next</p>
        <p className="journey__lede">{`${progress.done} of ${progress.total} facts are in. ${joinTitles('deploy')}. Not MVP yet.`}</p>
        <div className="journey-actions">
          <button type="button" onClick={onContinue}>
            Continue to Deploy
          </button>
        </div>
      </section>
    </>
  )
}

function ActionStep({
  item,
  items,
  index,
  total,
  progressLabel,
  onContinue,
  onBack,
}: {
  item: JourneyItemDef
  items: JourneyItemDef[]
  index: number
  total: number
  progressLabel: string
  onContinue: () => void
  onBack: () => void
}) {
  return (
    <>
      <StepDots items={items} index={index} label={progressLabel} />
      <p className="journey-count">{`${index + 1} of ${total}`}</p>
      <h1 className="journey__title">{item.title}</h1>
      <p className="journey__lede">{item.detail}</p>
      <div className="journey-actions">
        <button type="button" onClick={onContinue}>
          {item.actionLabel ?? 'Continue'}
        </button>
        <button type="button" className="button-secondary" onClick={onBack}>
          Back
        </button>
      </div>
    </>
  )
}

function DeployReview({
  state,
  progress,
  onEdit,
  onBack,
}: {
  state: JourneyState
  progress: { done: number; total: number }
  onEdit: (index: number) => void
  onBack: () => void
}) {
  return (
    <>
      <h1 className="journey__title">Ready</h1>
      <p className="journey__lede">{`${progress.done} of ${progress.total} platforms are marked. Build is later.`}</p>
      <div className="journey-list" aria-label="Deploy review">
        {DEPLOY.map((item, index) => (
          <button
            key={item.id}
            type="button"
            className="review-row"
            onClick={() => onEdit(index)}
          >
            <span className="review-row__title">{item.title}</span>
            <span className="review-row__value">{rowDetail(item, state[item.id])}</span>
          </button>
        ))}
      </div>
      <div className="journey-actions">
        <button type="button" className="button-secondary" onClick={onBack}>
          Back to Pre-req
        </button>
      </div>
    </>
  )
}

function StepDots({
  items,
  index,
  label,
}: {
  items: JourneyItemDef[]
  index: number
  label: string
}) {
  return (
    <ol className="step-dots" aria-label={label}>
      {items.map((entry, dot) => (
        <li
          key={entry.id}
          className={dot === index ? 'is-current' : dot < index ? 'is-done' : undefined}
        >
          <span className="visually-hidden">
            {entry.title}
            {dot === index ? ' (current)' : dot < index ? ' (done)' : ''}
          </span>
        </li>
      ))}
    </ol>
  )
}

function filledValues(
  item: JourneyItemDef,
  draft: Record<string, string>,
  current: ItemState,
): Record<string, string> {
  return Object.fromEntries(
    item.fields.map((field) => {
      const raw = draft[field.id]?.trim() ?? ''
      if (raw) return [field.id, raw]
      if (current.values[field.id]?.trim()) return [field.id, current.values[field.id]]
      if (field.input === 'password' && current.done) return [field.id, 'saved']
      return [field.id, '']
    }),
  )
}
