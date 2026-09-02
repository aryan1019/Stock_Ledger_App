import { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate, useParams } from 'react-router-dom'

import BreakEvenBar from '../components/BreakEvenBar'
import Icon from '../components/Icon'
import { Empty, ErrorNote, Loading } from '../components/States'
import {
  clearDetail, fetchStockDetail, selectDetail, selectDetailStatus, setPrice,
} from '../store/portfolioSlice'
import { deleteTransaction } from '../store/transactionsSlice'
import { money, pct, qty, shortDate, signed, toneOf } from '../utils/format'

export default function StockDetail() {
  const { stockId } = useParams()
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const detail = useSelector(selectDetail)
  const status = useSelector(selectDetailStatus)

  const [priceInput, setPriceInput] = useState('')
  const [editingPrice, setEditingPrice] = useState(false)

  useEffect(() => {
    dispatch(fetchStockDetail(stockId))
    return () => dispatch(clearDetail())
  }, [dispatch, stockId])

  if (status === 'loading' && !detail) return <Loading label="Rebuilding this position" />
  if (status === 'failed' || !detail) {
    return <Empty title="Nothing here yet" hint="No transactions have been recorded for this stock." />
  }

  const { stock, position, lots, transactions } = detail

  const savePrice = async () => {
    if (Number(priceInput) > 0) {
      await dispatch(setPrice({ stockId, price: priceInput }))
      dispatch(fetchStockDetail(stockId))
    }
    setEditingPrice(false)
    setPriceInput('')
  }

  const removeTxn = async (id) => {
    await dispatch(deleteTransaction(id))
    dispatch(fetchStockDetail(stockId))
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 330px', gap: 20, alignItems: 'start' }}>
      <div className="col" style={{ gap: 14 }}>
        {/* header */}
        <div className="row" style={{ alignItems: 'flex-start', gap: 18 }}>
          <button className="btn" style={{ height: 34, width: 34, padding: 0 }} onClick={() => navigate('/portfolio')}>
            <Icon name="back" size={17} />
          </button>
          <div className="col" style={{ gap: 5 }}>
            <div className="row" style={{ gap: 10, alignItems: 'baseline' }}>
              <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-.01em' }}>{stock.symbol}</span>
              <span className="mono faint" style={{ fontSize: 10.5, border: '1px solid var(--line)', borderRadius: 3, padding: '2px 6px' }}>
                {stock.exchange}
              </span>
              {stock.isin && <span className="mono faint" style={{ fontSize: 10.5 }}>{stock.isin}</span>}
            </div>
            <span className="muted" style={{ fontSize: 12 }}>{stock.company_name || '—'}</span>
          </div>

          <div className="grow" />

          {editingPrice ? (
            <div className="row" style={{ gap: 8 }}>
              <input
                autoFocus type="number" step="0.01" style={{ width: 140, height: 34 }}
                value={priceInput} onChange={(e) => setPriceInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && savePrice()}
                placeholder={detail.current_price}
              />
              <button className="btn btn-primary" style={{ height: 34 }} onClick={savePrice}>Save</button>
            </div>
          ) : (
            <div className="row" style={{ gap: 12, alignItems: 'baseline' }}>
              <span className="num" style={{ fontFamily: 'var(--cond)', fontSize: 30, fontWeight: 600 }}>
                {money(detail.current_price)}
              </span>
              <button className="btn" style={{ height: 34 }} onClick={() => setEditingPrice(true)}>
                {detail.has_price ? 'Update price' : 'Set price'}
              </button>
            </div>
          )}
        </div>

        {!detail.has_price && (
          <ErrorNote>
            No market price recorded — unrealized figures below assume your average cost. Set a price for real numbers.
          </ErrorNote>
        )}

        {/* metrics */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 1, background: 'var(--line)', border: '1px solid var(--line)', borderRadius: 6, overflow: 'hidden' }}>
          {[
            ['Quantity', qty(position?.quantity), 'default'],
            ['Avg cost', money(position?.average_cost), 'default'],
            ['Break-even', money(detail.break_even), 'accent'],
            ['Invested', money(position?.cost_basis), 'default'],
            ['Realized', signed(detail.realized_pnl), toneOf(detail.realized_pnl)],
            ['Total P&L', signed(detail.total_pnl), toneOf(detail.total_pnl)],
          ].map(([label, value, tone]) => (
            <div key={label} style={{ background: 'var(--surface)', padding: '11px 13px', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span className="label" style={{ color: tone === 'accent' ? 'var(--accent)' : 'var(--text-3)' }}>{label}</span>
              <span className={`mono ${tone === 'gain' ? 'gain' : tone === 'loss' ? 'loss' : tone === 'accent' ? 'accent' : ''}`} style={{ fontSize: 17, fontWeight: 500 }}>
                {value}
              </span>
            </div>
          ))}
        </div>

        <BreakEvenBar
          averageCost={position?.average_cost}
          breakEven={detail.break_even}
          currentPrice={detail.current_price}
          recoveryBreakEven={detail.recovery_break_even}
        />

        {/* lots */}
        <div className="col" style={{ gap: 8 }}>
          <div className="row" style={{ gap: 10 }}>
            <span className="label">Buy lots · {lots.length} open</span>
            <span className="faint" style={{ fontSize: 11.5 }}>
              Each purchase stays separate — its own cost, break-even and tax clock.
            </span>
          </div>
          <div className="card scroll-x" style={{ overflow: 'hidden' }}>
            <table>
              <thead>
                <tr>
                  <th>Acquired</th><th>Qty</th><th>Buy price</th><th>True cost</th>
                  <th style={{ color: 'var(--accent)' }}>Break-even</th>
                  <th>Held</th><th style={{ textAlign: 'center' }}>Term</th>
                  <th>Unrealized</th><th style={{ textAlign: 'left' }}>Tax clock</th>
                </tr>
              </thead>
              <tbody>
                {lots.map((lot) => (
                  <tr key={lot.id}>
                    <td className="muted">{shortDate(lot.acquisition_date)}</td>
                    <td>{qty(lot.remaining_qty)}</td>
                    <td>{money(lot.buy_price)}</td>
                    <td>{money(lot.cost_per_share)}</td>
                    <td className="accent">{money(lot.break_even)}</td>
                    <td className="muted">{lot.holding_days}d</td>
                    <td style={{ textAlign: 'center' }}>
                      <span className={`pill ${lot.term === 'LONG' ? 'pill-long' : 'pill-short'}`}>{lot.term}</span>
                    </td>
                    <td className={toneOf(lot.unrealized_pnl)}>{signed(lot.unrealized_pnl)}</td>
                    <td style={{ textAlign: 'left' }}>
                      {lot.days_to_long_term === 0 ? (
                        <span className="faint" style={{ fontSize: 11 }}>already long-term</span>
                      ) : (
                        <div className="row" style={{ gap: 9 }}>
                          <div style={{ width: 62, height: 4, background: 'var(--line-soft)', borderRadius: 2, overflow: 'hidden' }}>
                            <div style={{ width: `${Math.round(((365 - lot.days_to_long_term) / 365) * 100)}%`, height: 4, background: 'var(--warn)' }} />
                          </div>
                          <span className="muted" style={{ fontSize: 11 }}>{lot.days_to_long_term}d to long</span>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ---------------- right rail ---------------- */}
      <div className="col" style={{ gap: 16 }}>
        <div className="card col" style={{ padding: '13px 14px', gap: 10 }}>
          <span className="label">Broker reconciliation</span>
          <div className="col" style={{ gap: 7 }}>
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontSize: 12 }}>Your true average</span>
              <span className="mono" style={{ fontSize: 13 }}>{money(position?.average_cost)}</span>
            </div>
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span className="muted" style={{ fontSize: 12 }}>Your broker would show</span>
              <span className="mono muted" style={{ fontSize: 13 }}>{money(detail.broker_style_average)}</span>
            </div>
          </div>
          <div style={{ height: 1, background: 'var(--line-soft)' }} />
          <p className="faint" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.5 }}>
            The gap is your realized P&L, which brokers net into the cost of shares you still hold.
            This app never does.
          </p>
        </div>

        <div className="card col" style={{ padding: '13px 14px', gap: 10 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="label">Charges paid</span>
            <span className="mono warn" style={{ fontSize: 15, fontWeight: 500 }}>
              {money(detail.total_charges_paid)}
            </span>
          </div>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="faint" style={{ fontSize: 11.5 }}>Cost to exit at today's price</span>
            <span className="mono muted" style={{ fontSize: 12 }}>{money(detail.exit_charges)}</span>
          </div>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="faint" style={{ fontSize: 11.5 }}>Unrealized, net of exit</span>
            <span className={`mono ${toneOf(detail.unrealized_pnl_net)}`} style={{ fontSize: 12 }}>
              {signed(detail.unrealized_pnl_net)}
            </span>
          </div>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="faint" style={{ fontSize: 11.5 }}>Return on invested</span>
            <span className={`mono ${toneOf(detail.return_pct)}`} style={{ fontSize: 12 }}>
              {pct(detail.return_pct)}
            </span>
          </div>
        </div>

        <div className="col" style={{ gap: 8 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="label">Ledger · {transactions.length} entries</span>
            <button className="accent" style={{ fontSize: 11.5 }} onClick={() => navigate(`/add?stock=${stockId}`)}>
              Add
            </button>
          </div>
          <div className="col" style={{ gap: 6 }}>
            {transactions.map((t) => (
              <div key={t.id} className="card col" style={{ padding: '9px 11px', gap: 5 }}>
                <div className="row" style={{ gap: 8 }}>
                  <span className={`pill ${t.type === 'SELL' ? 'pill-sell' : 'pill-buy'}`}>{t.type}</span>
                  <span className="mono" style={{ fontSize: 11.5 }}>
                    {qty(t.quantity)} @ {money(t.price)}
                  </span>
                  <div className="grow" />
                  <span className="mono faint" style={{ fontSize: 10.5 }}>{shortDate(t.trade_date)}</span>
                  <button title="Delete" onClick={() => removeTxn(t.id)} style={{ display: 'flex' }}>
                    <Icon name="trash" size={13} color="var(--text-3)" />
                  </button>
                </div>
                <div className="row mono faint" style={{ justifyContent: 'space-between', fontSize: 10.5 }}>
                  <span>charges {money(t.total_charges)}</span>
                  <span>turnover {money(t.turnover)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
