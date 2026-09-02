import { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'

import { PRESETS, selectRange, setCustomRange, setPreset } from '../store/analyticsSlice'
import { today } from '../utils/format'

/** Presets for the common case, explicit dates when you need a precise window. */
export default function DateRangePicker() {
  const dispatch = useDispatch()
  const range = useSelector(selectRange)
  const [open, setOpen] = useState(range.custom)
  const [draft, setDraft] = useState({ from: range.from, to: range.to || today() })

  useEffect(() => {
    if (range.custom) setDraft({ from: range.from, to: range.to })
  }, [range.custom, range.from, range.to])

  const apply = () => {
    if (draft.from && draft.to && draft.from <= draft.to) {
      dispatch(setCustomRange(draft))
    }
  }

  const invalid = draft.from && draft.to && draft.from > draft.to

  return (
    <div className="col" style={{ gap: 8, alignItems: 'flex-end' }}>
      <div className="row" style={{ gap: 2, border: '1px solid var(--line)', borderRadius: 5, padding: 2 }}>
        {PRESETS.map((p) => {
          const on = !range.custom && range.preset === p.key
          return (
            <button
              key={p.key}
              onClick={() => { dispatch(setPreset(p.key)); setOpen(false) }}
              style={{
                padding: '5px 11px', fontSize: 12, borderRadius: 3, whiteSpace: 'nowrap',
                color: on ? 'var(--text)' : 'var(--text-3)',
                background: on ? 'var(--surface-3)' : 'transparent',
              }}
            >
              {p.label}
            </button>
          )
        })}
        <button
          onClick={() => setOpen((v) => !v)}
          style={{
            padding: '5px 11px', fontSize: 12, borderRadius: 3, whiteSpace: 'nowrap',
            color: range.custom ? 'var(--accent)' : 'var(--text-3)',
            background: range.custom ? 'var(--accent-dim)' : 'transparent',
          }}
        >
          Custom…
        </button>
      </div>

      {open && (
        <div className="card row" style={{ padding: '10px 12px', gap: 10, alignItems: 'flex-end' }}>
          <label className="col" style={{ gap: 5 }}>
            <span className="label">From</span>
            <input
              type="date" max={draft.to || today()} value={draft.from} style={{ height: 34, width: 150 }}
              onChange={(e) => setDraft((d) => ({ ...d, from: e.target.value }))}
            />
          </label>
          <label className="col" style={{ gap: 5 }}>
            <span className="label">To</span>
            <input
              type="date" max={today()} min={draft.from || undefined} value={draft.to}
              style={{ height: 34, width: 150 }}
              onChange={(e) => setDraft((d) => ({ ...d, to: e.target.value }))}
            />
          </label>
          <button
            className="btn btn-primary" style={{ height: 34 }}
            disabled={!draft.from || !draft.to || invalid}
            onClick={apply}
          >
            Apply
          </button>
        </div>
      )}

      {invalid && (
        <span className="loss" style={{ fontSize: 11 }}>The start date is after the end date.</span>
      )}
    </div>
  )
}
