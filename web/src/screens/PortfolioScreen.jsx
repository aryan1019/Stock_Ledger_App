import { useSelector, useDispatch } from 'react-redux'
import { useNavigate } from 'react-router-dom'

import BreakEvenBar from '../components/BreakEvenBar'
import StatTile from '../components/StatTile'
import { Empty, Loading } from '../components/States'
import {
  selectFilter, selectFilterCounts, selectPortfolioStatus, selectSummary,
  selectVisibleHoldings, setFilter,
} from '../store/portfolioSlice'
import { money, pct, qty, signed, toneOf } from '../utils/format'

const FILTERS = [
  { key: 'ALL', label: 'All' },
  { key: 'PROFIT', label: 'In profit' },
  { key: 'BELOW_BE', label: 'Below break-even' },
]

export default function PortfolioScreen() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const holdings = useSelector(selectVisibleHoldings)
  const counts = useSelector(selectFilterCounts)
  const filter = useSelector(selectFilter)
  const summary = useSelector(selectSummary)
  const status = useSelector(selectPortfolioStatus)

  if (status === 'loading' && !summary) return <Loading label="Loading holdings" />
  if (counts.ALL === 0) {
    return <Empty title="No holdings" hint="Record a transaction and your position will appear here." />
  }

  return (
    <div className="col" style={{ gap: 16 }}>
      <div className="row" style={{ gap: 16, flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>Portfolio</h1>
        <span className="mono faint" style={{ fontSize: 11 }}>
          {counts.ALL} HOLDING{counts.ALL === 1 ? '' : 'S'}
        </span>
        <div className="grow" />
        <div className="row" style={{ gap: 2, border: '1px solid var(--line)', borderRadius: 5, padding: 2 }}>
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => dispatch(setFilter(f.key))}
              style={{
                padding: '5px 11px', fontSize: 12, borderRadius: 3,
                color: filter === f.key ? 'var(--text)' : 'var(--text-3)',
                background: filter === f.key ? 'var(--surface-3)' : 'transparent',
              }}
            >
              {f.label} {counts[f.key]}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12 }}>
        <StatTile label="Market value" value={money(summary?.market_value)} />
        <StatTile label="Invested" value={money(summary?.invested)} tone="muted" />
        <StatTile label="Unrealized" value={signed(summary?.unrealized_pnl)} tone={toneOf(summary?.unrealized_pnl)} />
        <StatTile label="Realized (lifetime)" value={signed(summary?.realized_pnl)} tone={toneOf(summary?.realized_pnl)} />
        <StatTile label="Charges paid" value={money(summary?.total_charges_paid)} tone="warn" />
      </div>

      <div className="card scroll-x" style={{ overflow: 'hidden' }}>
        <table>
          <thead>
            <tr>
              <th>Stock</th><th>Qty</th><th>Avg cost</th><th>LTP</th>
              <th style={{ color: 'var(--accent)' }}>Break-even</th>
              <th>Invested</th><th>Mkt value</th><th>Unrealized</th><th>Realized</th>
              <th style={{ textAlign: 'left' }}>vs break-even</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => (
              <tr key={h.stock} className="clickable" onClick={() => navigate(`/portfolio/${h.stock}`)}>
                <td style={{ fontWeight: 500 }}>{h.symbol}</td>
                <td>{qty(h.quantity)}</td>
                <td>{money(h.average_cost)}</td>
                <td>{h.has_price ? money(h.current_price) : <span className="warn">not set</span>}</td>
                <td className="accent">{money(h.break_even)}</td>
                <td className="muted">{money(h.cost_basis)}</td>
                <td>{money(h.market_value)}</td>
                <td className={toneOf(h.unrealized_pnl)}>{signed(h.unrealized_pnl)}</td>
                <td className={Number(h.realized_pnl) === 0 ? 'faint' : toneOf(h.realized_pnl)}>
                  {Number(h.realized_pnl) === 0 ? '—' : signed(h.realized_pnl)}
                </td>
                <td style={{ textAlign: 'left' }}>
                  <div className="row" style={{ gap: 9 }}>
                    <BreakEvenBar compact averageCost={h.average_cost} breakEven={h.break_even} currentPrice={h.current_price} />
                    <span className={toneOf(h.vs_break_even_pct)} style={{ fontSize: 11 }}>{pct(h.vs_break_even_pct)}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="faint" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.5 }}>
        Break-even includes exit charges, so it always sits above average cost. The bar shows where
        today's price falls between the two.
      </p>
    </div>
  )
}
