import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate, useSearchParams } from 'react-router-dom'

import Icon from '../components/Icon'
import { ErrorNote } from '../components/States'
import { createStock, fetchStocks, selectAllStocks } from '../store/referenceSlice'
import {
  clearPreview, clearSubmit, createTransaction, previewTransaction,
  selectPreview, selectPreviewStatus, selectSubmitStatus, selectTransactionError,
} from '../store/transactionsSlice'
import { daysAgoISO, money, qty as fmtQty, signed, today } from '../utils/format'

const SIDES = [
  { value: 'BUY', label: 'BUY', icon: 'up', color: 'var(--gain)', bg: 'var(--gain-bg)' },
  { value: 'SELL', label: 'SELL', icon: 'down', color: 'var(--loss)', bg: 'var(--loss-bg)' },
]

export default function AddTransaction() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const stocks = useSelector(selectAllStocks)
  const preview = useSelector(selectPreview)
  const previewStatus = useSelector(selectPreviewStatus)
  const submitStatus = useSelector(selectSubmitStatus)
  const error = useSelector(selectTransactionError)

  const [form, setForm] = useState({
    stock: params.get('stock') || '',
    type: 'BUY',
    quantity: '',
    price: '',
    trade_date: today(),
    exchange: 'NSE',
  })
  const [symbolQuery, setSymbolQuery] = useState('')
  const [showList, setShowList] = useState(false)

  const selectedStock = useMemo(
    () => stocks.find((s) => String(s.id) === String(form.stock)),
    [stocks, form.stock],
  )

  useEffect(() => {
    dispatch(clearSubmit())
    return () => { dispatch(clearPreview()); dispatch(clearSubmit()) }
  }, [dispatch])

  // Debounced live preview — this is what makes charges visible before saving.
  useEffect(() => {
    const { stock, quantity, price, type, exchange } = form
    if (!stock || Number(quantity) <= 0 || Number(price) <= 0) {
      dispatch(clearPreview())
      return undefined
    }
    const t = setTimeout(() => {
      dispatch(previewTransaction({ stock, type, quantity, price, exchange }))
    }, 220)
    return () => clearTimeout(t)
  }, [dispatch, form])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const matches = useMemo(() => {
    const q = symbolQuery.trim().toUpperCase()
    if (!q) return stocks.slice(0, 6)
    return stocks.filter((s) => s.symbol.toUpperCase().includes(q)).slice(0, 6)
  }, [stocks, symbolQuery])

  const pickStock = (s) => {
    setForm((f) => ({ ...f, stock: String(s.id), exchange: s.exchange }))
    setSymbolQuery('')
    setShowList(false)
  }

  const addSymbol = async () => {
    const symbol = symbolQuery.trim().toUpperCase()
    if (!symbol) return
    const res = await dispatch(createStock({ symbol, exchange: form.exchange }))
    if (res.meta.requestStatus === 'fulfilled') {
      pickStock(res.payload)
      dispatch(fetchStocks())
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    const res = await dispatch(createTransaction(form))
    if (res.meta.requestStatus === 'fulfilled') navigate(`/portfolio/${form.stock}`)
  }

  const canSubmit =
    form.stock && Number(form.quantity) > 0 && Number(form.price) > 0 &&
    submitStatus !== 'saving' &&
    !(preview && preview.sufficient_quantity === false)

  const side = SIDES.find((s) => s.value === form.type)

  return (
    <div className="col" style={{ gap: 18 }}>
      <div className="row" style={{ alignItems: 'baseline', gap: 14 }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>Add transaction</h1>
        <span className="faint" style={{ fontSize: 12.5 }}>
          Nothing is saved until you confirm. The charges below are what your broker will bill.
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(380px, 580px) minmax(320px, 1fr)', gap: 22, alignItems: 'start' }}>
        {/* ---------------- form ---------------- */}
        <form onSubmit={submit} className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="row" style={{ gap: 8 }}>
            {SIDES.map((s) => {
              const on = form.type === s.value
              return (
                <button
                  key={s.value} type="button"
                  onClick={() => setForm((f) => ({ ...f, type: s.value }))}
                  style={{
                    flexGrow: 1, height: 46, display: 'flex', alignItems: 'center',
                    justifyContent: 'center', gap: 8, borderRadius: 6,
                    border: `${on ? 1.5 : 1}px solid ${on ? s.color : 'var(--line)'}`,
                    background: on ? s.bg : 'transparent',
                    color: on ? s.color : 'var(--text-3)',
                    fontSize: 14, fontWeight: on ? 600 : 500,
                  }}
                >
                  <Icon name={s.icon} size={15} strokeWidth={2.2} />
                  {s.label}
                </button>
              )
            })}
          </div>

          <div className="col" style={{ gap: 7, position: 'relative' }}>
            <span className="label">Stock</span>
            {selectedStock && !showList ? (
              <button
                type="button"
                onClick={() => { setShowList(true); setSymbolQuery('') }}
                style={{
                  height: 46, border: '1px solid var(--line)', borderRadius: 6,
                  background: 'var(--raised)', display: 'flex', alignItems: 'center',
                  padding: '0 13px', gap: 11, textAlign: 'left',
                }}
              >
                <div className="col" style={{ gap: 2, flexGrow: 1 }}>
                  <span className="mono" style={{ fontSize: 14, fontWeight: 500 }}>{selectedStock.symbol}</span>
                  <span className="faint" style={{ fontSize: 10.5 }}>
                    {selectedStock.company_name || selectedStock.exchange}
                  </span>
                </div>
                <span className="faint" style={{ fontSize: 11 }}>change</span>
              </button>
            ) : (
              <>
                <div className="row" style={{ position: 'relative' }}>
                  <span style={{ position: 'absolute', left: 12, display: 'flex' }}>
                    <Icon name="search" size={15} color="var(--text-3)" />
                  </span>
                  <input
                    autoFocus value={symbolQuery} placeholder="Search or type a new symbol"
                    onChange={(e) => setSymbolQuery(e.target.value.toUpperCase())}
                    onFocus={() => setShowList(true)}
                    style={{ paddingLeft: 36 }}
                  />
                </div>
                <div className="card" style={{ background: 'var(--surface-2)', overflow: 'hidden' }}>
                  {matches.map((s) => (
                    <button
                      key={s.id} type="button" onClick={() => pickStock(s)}
                      style={{ width: '100%', padding: '9px 13px', display: 'flex', gap: 12, alignItems: 'center', textAlign: 'left' }}
                    >
                      <span className="mono" style={{ fontSize: 12.5, width: 100 }}>{s.symbol}</span>
                      <span className="faint grow" style={{ fontSize: 12 }}>{s.company_name}</span>
                      <span className="mono faint" style={{ fontSize: 10 }}>{s.exchange}</span>
                    </button>
                  ))}
                  {symbolQuery && !matches.some((m) => m.symbol === symbolQuery) && (
                    <button
                      type="button" onClick={addSymbol}
                      style={{ width: '100%', padding: '10px 13px', display: 'flex', gap: 10, alignItems: 'center', borderTop: '1px solid var(--line-soft)' }}
                    >
                      <Icon name="plus" size={14} color="var(--accent)" />
                      <span className="accent" style={{ fontSize: 12.5 }}>Add “{symbolQuery}” to my stocks</span>
                    </button>
                  )}
                </div>
              </>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <label className="col" style={{ gap: 7 }}>
              <span className="label">Quantity</span>
              <input type="number" min="0" step="any" value={form.quantity} onChange={set('quantity')} placeholder="0" />
            </label>
            <label className="col" style={{ gap: 7 }}>
              <span className="label">Price</span>
              <input type="number" min="0" step="0.01" value={form.price} onChange={set('price')} placeholder="0.00" />
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="col" style={{ gap: 7 }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <span className="label">Trade date</span>
                <button type="button" className="accent" style={{ fontSize: 10.5 }}
                  onClick={() => setForm((f) => ({ ...f, trade_date: daysAgoISO(1) }))}>
                  yesterday
                </button>
              </div>
              <input type="date" max={today()} value={form.trade_date} onChange={set('trade_date')} />
            </div>
            <div className="col" style={{ gap: 7 }}>
              <span className="label">Exchange</span>
              <div className="row" style={{ gap: 8, height: 44 }}>
                {['NSE', 'BSE'].map((x) => {
                  const on = form.exchange === x
                  return (
                    <button
                      key={x} type="button" onClick={() => setForm((f) => ({ ...f, exchange: x }))}
                      style={{
                        flexGrow: 1, height: '100%', borderRadius: 6,
                        border: `${on ? 1.5 : 1}px solid ${on ? 'var(--accent)' : 'var(--line)'}`,
                        background: on ? 'var(--accent-dim)' : 'transparent',
                        color: on ? 'var(--accent)' : 'var(--text-3)',
                        fontFamily: 'var(--mono)', fontSize: 13,
                      }}
                    >
                      {x}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          <ErrorNote>{error}</ErrorNote>

          <div className="row" style={{ gap: 10 }}>
            <button type="button" className="btn" style={{ height: 46 }} onClick={() => navigate(-1)}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary grow" style={{ height: 46 }} disabled={!canSubmit}>
              {submitStatus === 'saving' ? (
                <span className="spinner" />
              ) : (
                `Record ${form.type}${selectedStock ? ` · ${fmtQty(form.quantity || 0)} ${selectedStock.symbol}` : ''}`
              )}
            </button>
          </div>
        </form>

        {/* ---------------- live preview ---------------- */}
        <div className="col" style={{ gap: 14 }}>
          <div className="row" style={{ gap: 9 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)' }} />
            <span className="label accent">Live preview — updates as you type</span>
            {previewStatus === 'loading' && <span className="spinner" style={{ width: 12, height: 12 }} />}
          </div>

          {!preview ? (
            <div className="card" style={{ padding: 26 }}>
              <p className="faint" style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6 }}>
                Pick a stock and enter a quantity and price. Every charge your broker applies —
                STT, stamp duty, exchange fees, GST and the DP charge — appears here before you commit,
                along with what your average cost and break-even become.
              </p>
            </div>
          ) : (
            <>
              {preview.sufficient_quantity === false && (
                <ErrorNote>
                  You hold {fmtQty(preview.held_quantity)} on this date. Add the missing BUY, or
                  record an opening balance first.
                </ErrorNote>
              )}

              <div className="card" style={{ overflow: 'hidden' }}>
                <div className="row" style={{ padding: '12px 16px', borderBottom: '1px solid var(--line-soft)', alignItems: 'baseline' }}>
                  <span className="label">Charges · {preview.plan}</span>
                  <div className="grow" />
                  <span className="mono faint" style={{ fontSize: 10.5 }}>turnover {money(preview.turnover)}</span>
                </div>
                <div style={{ padding: '6px 16px 13px' }}>
                  {preview.charges.map((c) => (
                    <div key={c.code} className="row mono" style={{ justifyContent: 'space-between', padding: '6px 0', fontSize: 12.5 }}>
                      <span className="muted">{c.label}</span>
                      <span className={Number(c.amount) === 0 ? 'gain' : ''}>{money(c.amount)}</span>
                    </div>
                  ))}
                  <div style={{ height: 1, background: 'var(--line)', margin: '8px 0' }} />
                  <div className="row mono" style={{ justifyContent: 'space-between', fontSize: 14, fontWeight: 600 }}>
                    <span>Total charges</span>
                    <span className="warn">{money(preview.total_charges)}</span>
                  </div>
                  <div className="row mono" style={{ justifyContent: 'space-between', paddingTop: 7, fontSize: 12.5 }}>
                    <span className="faint">{form.type === 'BUY' ? 'Debited from your account' : 'Credited to your account'}</span>
                    <span className="muted">{money(preview.net_amount)}</span>
                  </div>
                </div>
              </div>

              <div className="card" style={{ overflow: 'hidden' }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--line-soft)' }}>
                  <span className="label">
                    Your {selectedStock?.symbol} position after this trade
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 34px 1fr', padding: '14px 16px', alignItems: 'start' }}>
                  <Side title="Now" data={preview.before} dim />
                  <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 26 }}>
                    <Icon name="right" size={17} color="var(--accent)" />
                  </div>
                  <Side title="After" data={preview.after} />
                </div>

                {(preview.average_cost_delta || preview.realized_pnl) && (
                  <div style={{ padding: '10px 16px 13px', borderTop: '1px solid var(--line-soft)' }}>
                    {preview.realized_pnl ? (
                      <p className="faint" style={{ margin: 0, fontSize: 12, lineHeight: 1.5 }}>
                        This sale realizes{' '}
                        <span className={Number(preview.realized_pnl) >= 0 ? 'gain' : 'loss'}>
                          {signed(preview.realized_pnl)}
                        </span>
                        . Your remaining shares keep their average of {money(preview.before.average_cost)} —
                        realized profit is never used to make it look lower.
                      </p>
                    ) : (
                      <p className="faint" style={{ margin: 0, fontSize: 12, lineHeight: 1.5 }}>
                        Your average {Number(preview.average_cost_delta) >= 0 ? 'rises' : 'falls'} by{' '}
                        {money(Math.abs(Number(preview.average_cost_delta)))} — this is a new lot, and your
                        existing shares keep their own cost and tax clock.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function Side({ title, data, dim = false }) {
  const rows = [
    ['Qty', fmtQty(data.quantity)],
    ['Avg cost', money(data.average_cost)],
    ['Break-even', money(data.break_even)],
    ['Invested', money(data.cost_basis)],
  ]
  return (
    <div className="col" style={{ gap: 11 }}>
      <span className="label" style={{ color: dim ? 'var(--text-3)' : 'var(--accent)' }}>{title}</span>
      <div className="col" style={{ gap: 8 }}>
        {rows.map(([k, v], i) => (
          <div key={k} className="row mono" style={{ justifyContent: 'space-between' }}>
            <span className="faint" style={{ fontSize: 11.5 }}>{k}</span>
            <span
              style={{
                fontSize: 13,
                color: dim ? 'var(--text-2)' : i === 2 ? 'var(--accent)' : 'var(--text)',
                fontWeight: dim ? 400 : 500,
              }}
            >
              {v}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
