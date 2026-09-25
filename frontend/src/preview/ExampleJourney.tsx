import { useState } from 'react'
import {
  PHASES,
  fieldsFilled,
  itemsForPhase,
  overallProgress,
  phaseProgress,
  prereqReady,
  type ItemState,
  type JourneyItemDef,
  type JourneyState,
} from './exampleData'

export function ExampleJourney({
  state,
  onChange,
}: {
  state: JourneyState
  onChange: (next: JourneyState) => void
}) {
  const [error, setError] = useState<string | null>(null)
  const progress = overallProgress(state)

  function updateItem(id: string, next: ItemState) {
    onChange({ ...state, [id]: next })
  }

  return (
    <div className="journey-shell">
      <main className="journey" aria-label="checklist">
        <h1 className="journey__title">The Shed</h1>
        <p className="journey__lede">
          {`Facts first. Then the container. Platforms later. ${progress.done} of ${progress.total}.`}
        </p>
        {error && <p role="alert">{error}</p>}

        {PHASES.map((phase) => {
          const count = phaseProgress(phase.id, state)
          return (
            <section key={phase.id} className="checklist-section" aria-labelledby={`phase-${phase.id}`}>
              <header className="checklist-section__head">
                <h2 id={`phase-${phase.id}`} className="checklist-section__title">
                  {phase.title}
                </h2>
                <p className="checklist-section__lede">
                  {`${phase.lede} ${count.done} of ${count.total}.`}
                </p>
              </header>
              <div className="journey-list">
                {itemsForPhase(phase.id).map((item) => (
                  <CheckRow
                    key={item.id}
                    item={item}
                    current={state[item.id] ?? { values: {}, done: false }}
                    state={state}
                    onChange={(next) => updateItem(item.id, next)}
                    onError={setError}
                  />
                ))}
              </div>
            </section>
          )
        })}
      </main>
    </div>
  )
}

function CheckRow({
  item,
  current,
  state,
  onChange,
  onError,
}: {
  item: JourneyItemDef
  current: ItemState
  state: JourneyState
  onChange: (next: ItemState) => void
  onError: (message: string | null) => void
}) {
  function setValue(fieldId: string, value: string) {
    onChange({
      ...current,
      done: false,
      values: { ...current.values, [fieldId]: value },
    })
  }

  function toggle(checked: boolean) {
    onError(null)
    if (!checked) {
      onChange({ ...current, done: false })
      return
    }
    if (item.fields.length && !fieldsFilled(item, current)) {
      onError(`${item.fields[0].label} is required`)
      return
    }
    if (item.id === 'validation' && !prereqReady(state)) {
      onError('Finish Pre-req first.')
      return
    }
    const values = Object.fromEntries(
      item.fields.map((field) => {
        const raw = current.values[field.id]?.trim() ?? ''
        if (field.input === 'password') return [field.id, raw || 'saved']
        return [field.id, raw]
      }),
    )
    onChange({ values, done: true })
  }

  return (
    <div className="check-row" data-done={current.done ? 'true' : 'false'}>
      <input
        id={`check-${item.id}`}
        type="checkbox"
        checked={current.done}
        onChange={(e) => toggle(e.target.checked)}
      />
      <div className="check-row__body">
        <label htmlFor={`check-${item.id}`} className="check-row__title">
          {item.title}
        </label>
        <p className="check-row__hint">{item.detail}</p>
        {item.id === 'validation' && !current.done ? (
          <ul className="journey-checks" aria-label="prerequisite checks">
            {itemsForPhase('prereq').map((entry) => {
              const ready = Boolean(state[entry.id]?.done)
              return (
                <li key={entry.id} data-status={ready ? 'pass' : 'missing'}>
                  <span>{entry.title}</span>
                  <span>{ready ? 'Ready' : 'Missing'}</span>
                </li>
              )
            })}
          </ul>
        ) : null}
        {item.fields.map((field) => {
          const id = `journey-${item.id}-${field.id}`
          return (
            <div key={field.id} className="journey-field">
              <label htmlFor={id}>{field.label}</label>
              {field.input === 'textarea' ? (
                <textarea
                  id={id}
                  value={current.done && field.input === 'textarea' ? '' : (current.values[field.id] ?? '')}
                  placeholder={current.done ? 'Saved. Paste a new key to replace it.' : field.placeholder}
                  onChange={(e) => setValue(field.id, e.target.value)}
                />
              ) : (
                <input
                  id={id}
                  type={field.input}
                  value={
                    current.done && field.input === 'password' ? '' : (current.values[field.id] ?? '')
                  }
                  placeholder={
                    current.done && field.input === 'password'
                      ? 'Saved. Paste a new value to replace it.'
                      : field.placeholder
                  }
                  autoComplete="off"
                  onChange={(e) => setValue(field.id, e.target.value)}
                />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
