import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'

import Icon from '../components/Icon'
import { Empty, Loading } from '../components/States'
import {
  deleteTransaction, fetchTransactions, selectAllTransactions,
} from '../store/transactionsSlice'
import { money, qty, shortDate, today } from '../utils/format'

const TYPES = [
  { key: '', label: 'All' },
  { key: 'BUY', label: 'Buys' },
  { key: 'SELL', label: 'Sells' },
  { key: 'OPENING_BALANCE', label: 'Opening' },
]

const CHARGE_ORDER = ['BROKERAGE', 'STT', 'STAMP', 'EXCH_TXN', 'SEBI', 'DP', 'GST', 'MANUAL']

export default function Ledger() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const rows = useSelector(selectAllTransactions)
  const status = useSelector((s) => s.transactions.status)

  const [filters, setFilters] = useState({ type: '', q: '', from: '', to: '' })
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v))
    const t = setTimeout(() => dispatch(fetchTransactions(params)), 200)
    return () => clearTimeout(t)
  }, [dispatch, filters])

  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }))
  const anyFilter = Object.values(filters).some(Boolean)

  const totals = useMemo(
    () =>
      rows.reduce(
        (acc, t) => ({
          charges: acc.charges + Number(t.total_charges),
          bought: acc.bought + (t.type === 'BUY' ? Number(t.turnover) : 0),
          sold: acc.sold + (t.type === 'SELL' ? Number(t.turnover) : 0),
        }),
        { charges: 0, bought: 0, sold: 0 },
      ),
    [rows],
  )

  if (status === 'loading' && rows.length === 0 && !anyFilter) {
    return <Loading label="Loading the ledger" />
  }

  return (
    <div className="col" style={{ gap: 16 }}>
      <div className="row" style={{ gap: 14, flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>Ledger</h1>
        <span className="faint" style={{ fontSize: 12.5 }}>
          Every transaction, with the charges it was costed with frozen onto it. Append-only —
          deleting supersedes a row and replays, so history is never lost.
        </span>
      </div>

      {/* ---------- filters ---------- */}
      <div className="card row" style={{ padding: '11px 14px', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div className="row" style={{ gap: 2, border: '1px solid var(--line)', borderRadius: 5, padding: 2 }}>
          {TYPES.map((t) => {
            const on = filters.type === t.key
            return (
              <button
                key={t.key || 'all'}
                onClick={() => setFilters((f) => ({ ...f, type: t.key }))}
                style={{
                  padding: '5px 11px', fontSize: 12, borderRadius: 3,
                  color: on ? 'var(--text)' : 'var(--text-3)',
                  background: on ? 'var(--surface-3)' : 'transparent',
                }}
              >
                {t.label}
              </button>
            )
          })}
        </div>

        <div className="row" style={{ position: 'relative', width: 190 }}>
          <span style={{ position: 'absolute', left: 11, display: 'flex' }}>
            <Icon name="search" size={14} color="var(--text-3)" />
          </span>
          <input
            value={filters.q} onChange={set('q')} placeholder="Symbol"
            style={{ height: 36, paddingLeft: 33, fontSize: 13 }}
          />
        </div>

        <label className="col" style={{ gap: 5 }}>
          <span className="label">From</span>
          <input type="date" max={filters.to || today()} value={filters.from} onChange={set('from')}
            style={{ height: 36, width: 148, fontSize: 13 }} />
        </label>
        <label className="col" style={{ gap: 5 }}>
          <span className="label">To</span>
          <input type="date" max={today()} min={filters.from || undefined} value={filters.to} onChange={set('to')}
            style={{ height: 36, width: 148, fontSize: 13 }} />
        </label>

        {anyFilter && (
          <button className="btn" style={{ height: 36 }}
            onClick={() => setFilters({ type: '', q: '', from: '', to: '' })}>
            <Icon name="close" size={13} />
            Clear
          </button>
        )}

        <div className="grow" />

        <div className="row mono" style={{ gap: 18, fontSize: 11.5 }}>
          <span className="faint">{rows.length} row{rows.length === 1 ? '' : 's'}</span>
          <span className="faint">bought <span className="muted">{money(totals.bought)}</span></span>
          <span className="faint">sold <span className="muted">{money(totals.sold)}</span></span>
          <span className="faint">charges <span className="warn">{money(totals.charges)}</span></span>
        </div>
      </div>

      {rows.length === 0 ? (
        <Empty
          title={anyFilter ? 'Nothing matches those filters' : 'The ledger is empty'}
          hint={
            anyFilter
              ? 'Try a wider date range, or clear the filters.'
              : 'Every trade you record appears here.'
          }
        />
      ) : (
        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="scroll-x">
            <table>
              <thead>
                <tr>
                  <th>Date</th><th style={{ textAlign: 'left' }}>Type</th>
                  <th style={{ textAlign: 'left' }}>Stock</th>
                  <th>Qty</th><th>Price</th><th>Turnover</th><th>Charges</th>
                  <th>Net</th><th style={{ textAlign: 'left' }} /><th />
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => {
                  const isBuy = t.type !== 'SELL'
                  const net = isBuy
                    ? Number(t.turnover) + Number(t.total_charges)
                    : Number(t.turnover) - Number(t.total_charges)
                  const open = expanded === t.id
                  return (
                    <>
                      <tr key={t.id}>
                        <td className="muted">{shortDate(t.trade_date)}</td>
                        <td style={{ textAlign: 'left' }}>
                          <span className={`pill ${t.type === 'SELL' ? 'pill-sell' : 'pill-buy'}`}>
                            {t.type === 'OPENING_BALANCE' ? 'OPENING' : t.type}
                          </span>
                        </td>
                        <td
                          style={{ textAlign: 'left', fontWeight: 500, cursor: 'pointer' }}
                          onClick={() => navigate(`/portfolio/${t.stock}`)}
                        >
                          {t.symbol}
                        </td>
                        <td>{qty(t.quantity)}</td>
                        <td>{money(t.price)}</td>
                        <td className="muted">{money(t.turnover)}</td>
                        <td className="warn">{money(t.total_charges)}</td>
                        <td>{money(net)}</td>
                        <td style={{ textAlign: 'left' }}>
                          <button
                            className="faint"
                            style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}
                            onClick={() => setExpanded(open ? null : t.id)}
                          >
                            <span style={{ transform: open ? 'rotate(90deg)' : 'none', display: 'flex' }}>
                              <Icon name="right" size={12} />
                            </span>
                            charges
                          </button>
                        </td>
                        <td>
                          <button title="Delete" onClick={() => dispatch(deleteTransaction(t.id))} style={{ display: 'flex' }}>
                            <Icon name="trash" size={13} color="var(--text-3)" />
                          </button>
                        </td>
                      </tr>
                      {open && (
                        <tr key={`${t.id}-detail`}>
                          <td colSpan={10} style={{ background: 'var(--raised)', padding: '12px 16px', textAlign: 'left' }}>
                            <div className="row" style={{ gap: 26, flexWrap: 'wrap' }}>
                              {CHARGE_ORDER.filter((c) => t.charge_breakdown?.[c] !== undefined).map((code) => (
                                <div key={code} className="col" style={{ gap: 3 }}>
                                  <span className="label">{code}</span>
                                  <span className="mono" style={{ fontSize: 12.5 }}>
                                    {money(t.charge_breakdown[code])}
                                  </span>
                                </div>
                              ))}
                              <div className="col" style={{ gap: 3 }}>
                                <span className="label" style={{ color: 'var(--warn)' }}>Total</span>
                                <span className="mono warn" style={{ fontSize: 12.5, fontWeight: 600 }}>
                                  {money(t.total_charges)}
                                </span>
                              </div>
                              <div className="col grow" style={{ gap: 3, minWidth: 200 }}>
                                <span className="label">Exchange</span>
                                <span className="mono faint" style={{ fontSize: 11.5 }}>
                                  {t.exchange} · recorded {shortDate(t.created_at?.slice(0, 10))}
                                </span>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
