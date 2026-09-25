import { useState, type FormEvent } from 'react'
import {
  JOURNEY_ITEMS,
  PHASES,
  fieldsFilled,
  itemById,
  itemsForPhase,
  phaseProgress,
  prereqReady,
  rowDetail,
  type ItemState,
  type JourneyItemDef,
  type JourneyState,
  type LayoutId,
  type PhaseId,
} from './exampleData'

type OverviewScreen = { name: 'home' } | { name: 'phase'; phase: PhaseId } | { name: 'item'; itemId: string }

export function ExampleJourney({
  state,
  onChange,
}: {
  state: JourneyState
  onChange: (next: JourneyState) => void
}) {
  const [layout, setLayout] = useState<LayoutId>('overview')
  const [screen, setScreen] = useState<OverviewScreen>({ name: 'home' })
  const [focusIndex, setFocusIndex] = useState(0)

  function openLayout(next: LayoutId) {
    setLayout(next)
    if (next === 'overview') setScreen({ name: 'home' })
    else setFocusIndex(0)
  }

  return (
    <div className="journey-shell">
      <header className="journey-toolbar">
        <p className="journey-wordmark">The Shed</p>
        <div className="segmented" role="tablist" aria-label="layout">
          <button
            type="button"
            role="tab"
            aria-selected={layout === 'overview'}
            onClick={() => openLayout('overview')}
          >
            Overview
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={layout === 'focus'}
            onClick={() => openLayout('focus')}
          >
            One at a time
          </button>
        </div>
      </header>

      {layout === 'overview' ? (
        <Overview
          screen={screen}
          setScreen={setScreen}
          state={state}
          onChange={onChange}
        />
      ) : (
        <FocusStep
          index={focusIndex}
          setIndex={setFocusIndex}
          state={state}
          onChange={onChange}
          onDone={() => openLayout('overview')}
        />
      )}
    </div>
  )
}

function Overview({
  screen,
  setScreen,
  state,
  onChange,
}: {
  screen: OverviewScreen
  setScreen: (screen: OverviewScreen) => void
  state: JourneyState
  onChange: (next: JourneyState) => void
}) {
  if (screen.name === 'item') {
    const item = itemById(screen.itemId)
    if (!item) return null
    return (
      <ItemPane
        key={item.id}
        item={item}
        state={state}
        onChange={onChange}
        onBack={() => setScreen({ name: 'phase', phase: item.phase })}
        backLabel={PHASES.find((phase) => phase.id === item.phase)?.title ?? 'Back'}
      />
    )
  }

  if (screen.name === 'phase') {
    const phase = PHASES.find((entry) => entry.id === screen.phase)
    if (!phase) return null
    const progress = phaseProgress(phase.id, state)
    return (
      <main className="journey" aria-label={phase.title}>
        <button type="button" className="journey-back" onClick={() => setScreen({ name: 'home' })}>
          The Shed
        </button>
        <h1 className="journey__title">{phase.title}</h1>
        <p className="journey__lede">{`${phase.lede} ${progress.done} of ${progress.total}.`}</p>
        <PhaseList
          phase={phase.id}
          state={state}
          onOpen={(itemId) => setScreen({ name: 'item', itemId })}
        />
      </main>
    )
  }

  return (
    <main className="journey" aria-label="journey home">
      <h1 className="journey__title">The Shed</h1>
      <p className="journey__lede">Facts first. Then the container. Platforms later.</p>
      <div className="journey-list">
        {PHASES.map((phase) => {
          const progress = phaseProgress(phase.id, state)
          return (
            <button
              key={phase.id}
              type="button"
              className="journey-row"
              onClick={() => setScreen({ name: 'phase', phase: phase.id })}
            >
              <span className="journey-row__copy">
                <span className="journey-row__title">{phase.title}</span>
                <span className="journey-row__hint">{phase.lede}</span>
              </span>
              <span className="journey-row__meta">
                {progress.done === progress.total ? 'Ready' : `${progress.done} of ${progress.total}`}
              </span>
              <span className="journey-row__chevron" aria-hidden="true">
                ›
              </span>
            </button>
          )
        })}
      </div>
    </main>
  )
}

function PhaseList({
  phase,
  state,
  onOpen,
}: {
  phase: PhaseId
  state: JourneyState
  onOpen: (itemId: string) => void
}) {
  return (
    <div className="journey-list">
      {itemsForPhase(phase).map((item) => {
        const complete = fieldsFilled(item, state[item.id])
        return (
          <button
            key={item.id}
            type="button"
            className="journey-row"
            onClick={() => onOpen(item.id)}
          >
            <span className="journey-row__copy">
              <span className="journey-row__title">{item.title}</span>
              <span className="journey-row__hint">{rowDetail(item, state[item.id])}</span>
            </span>
            <span className={complete ? 'journey-row__check' : 'journey-row__meta'} aria-hidden="true">
              {complete ? '✓' : ''}
            </span>
            <span className="journey-row__chevron" aria-hidden="true">
              ›
            </span>
          </button>
        )
      })}
    </div>
  )
}

function FocusStep({
  index,
  setIndex,
  state,
  onChange,
  onDone,
}: {
  index: number
  setIndex: (index: number) => void
  state: JourneyState
  onChange: (next: JourneyState) => void
  onDone: () => void
}) {
  const item = JOURNEY_ITEMS[index]
  const phase = PHASES.find((entry) => entry.id === item.phase)
  return (
    <ItemPane
      key={item.id}
      item={item}
      state={state}
      onChange={onChange}
      eyebrow={`${phase?.title ?? ''} · ${index + 1} of ${JOURNEY_ITEMS.length}`}
      onBack={index === 0 ? onDone : () => setIndex(index - 1)}
      backLabel={index === 0 ? 'Overview' : JOURNEY_ITEMS[index - 1].title}
      onContinue={() => {
        if (index === JOURNEY_ITEMS.length - 1) onDone()
        else setIndex(index + 1)
      }}
    />
  )
}

function ItemPane({
  item,
  state,
  onChange,
  onBack,
  backLabel,
  onContinue,
  eyebrow,
}: {
  item: JourneyItemDef
  state: JourneyState
  onChange: (next: JourneyState) => void
  onBack: () => void
  backLabel: string
  onContinue?: () => void
  eyebrow?: string
}) {
  const current = state[item.id] ?? { values: {}, done: false }
  const [draft, setDraft] = useState(current.values)
  const [error, setError] = useState<string | null>(null)

  function updateItem(next: ItemState) {
    onChange({ ...state, [item.id]: next })
  }

  function handleSave(e?: FormEvent) {
    e?.preventDefault()
    setError(null)
    if (item.fields.length) {
      const missing = item.fields.find((field) => !draft[field.id]?.trim() && !current.done)
      if (missing) {
        setError(`${missing.label} is required`)
        return
      }
      updateItem({ values: valuesFromDraft(item, draft, current), done: true })
    } else if (item.id === 'validation') {
      if (!prereqReady(state)) {
        setError('Finish Pre-req first.')
        return
      }
      updateItem({ values: {}, done: true })
    } else {
      updateItem({ values: {}, done: true })
    }
    if (onContinue) onContinue()
    else onBack()
  }

  return (
    <main className="journey" aria-label={item.title}>
      <button type="button" className="journey-back" onClick={onBack}>
        {backLabel}
      </button>
      {eyebrow ? <p className="journey-kicker">{eyebrow}</p> : null}
      <h1 className="journey__title">{item.title}</h1>
      <p className="journey__lede">{item.detail}</p>

      {item.id === 'validation' ? <ValidationList state={state} /> : null}

      <form className="journey-form" onSubmit={handleSave}>
        {item.fields.map((field) => {
          const id = `journey-${item.id}-${field.id}`
          return (
            <div key={field.id} className="journey-field">
              <label htmlFor={id}>{field.label}</label>
              {field.input === 'textarea' ? (
                <textarea
                  id={id}
                  value={draft[field.id] ?? ''}
                  placeholder={current.done && field.input === 'textarea' ? 'Saved. Paste a new key to replace it.' : field.placeholder}
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
          <button type="submit">{item.actionLabel ?? (onContinue ? 'Continue' : 'Save')}</button>
        </div>
      </form>
    </main>
  )
}

function valuesFromDraft(
  item: JourneyItemDef,
  draft: Record<string, string>,
  current: ItemState,
): Record<string, string> {
  return Object.fromEntries(
    item.fields.map((field) => {
      const raw = draft[field.id]?.trim() ?? ''
      if (field.input === 'password') return [field.id, raw || current.values[field.id] || 'saved']
      return [field.id, raw || current.values[field.id] || '']
    }),
  )
}

function ValidationList({ state }: { state: JourneyState }) {
  return (
    <ul className="journey-checks" aria-label="prerequisite checks">
      {itemsForPhase('prereq').map((item) => {
        const ready = fieldsFilled(item, state[item.id])
        return (
          <li key={item.id} data-status={ready ? 'pass' : 'missing'}>
            <span>{item.title}</span>
            <span>{ready ? 'Ready' : 'Missing'}</span>
          </li>
        )
      })}
    </ul>
  )
}
