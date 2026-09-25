import { useState, type FormEvent } from 'react'
import {
  fieldsFilled,
  itemsForPhase,
  phaseProgress,
  rowDetail,
  type ItemState,
  type JourneyItemDef,
  type JourneyState,
} from './exampleData'

const PREREQ = itemsForPhase('prereq')

export function ExampleJourney({
  state,
  onChange,
}: {
  state: JourneyState
  onChange: (next: JourneyState) => void
}) {
  const [step, setStep] = useState(0)
  const progress = phaseProgress('prereq', state)
  const reviewing = step >= PREREQ.length
  const item = reviewing ? null : PREREQ[step]

  function saveItem(itemDef: JourneyItemDef, values: Record<string, string>): JourneyState {
    const next = {
      ...state,
      [itemDef.id]: { values, done: true },
    }
    onChange(next)
    return next
  }

  return (
    <div className="journey-shell">
      <main className="journey" aria-label="Pre-req">
        <p className="journey-kicker">Pre-req</p>
        {reviewing ? (
          <Review state={state} progress={progress} onEdit={(index) => setStep(index)} />
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
      <ol className="step-dots" aria-label="Pre-req progress">
        {PREREQ.map((entry, dot) => (
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

function Review({
  state,
  progress,
  onEdit,
}: {
  state: JourneyState
  progress: { done: number; total: number }
  onEdit: (index: number) => void
}) {
  return (
    <>
      <h1 className="journey__title">Ready</h1>
      <p className="journey__lede">{`${progress.done} of ${progress.total} facts are in. Bootstrap is next.`}</p>
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
    </>
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
