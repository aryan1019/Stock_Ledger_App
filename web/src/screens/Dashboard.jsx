import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'

import BreakEvenBar from '../components/BreakEvenBar'
import DateRangePicker from '../components/DateRangePicker'
import Icon from '../components/Icon'
import StatTile from '../components/StatTile'
import { Empty, ErrorNote, Loading } from '../components/States'
import {
  ChargeBreakdownChart, ChartFrame, CumulativePnlChart, PeriodPnlChart, RealizedByStockChart,
} from '../components/charts'
import {
  fetchAnalytics, selectAnalytics, selectAnalyticsStatus, selectByStock,
  selectChargeComponents, selectRange, selectRecentClosedTrades, selectSeries,
} from '../store/analyticsSlice'
import {
  selectAllHoldings, selectPortfolioStatus, selectSummary,
} from '../store/portfolioSlice'
import { money, pct, qty, shortDate, signed, toneOf } from '../utils/format'

export default function Dashboard() {
  const dispatch = useDispatch()
  const navigate = useNavigate()

  const holdings = useSelector(selectAllHoldings)
  const summary = useSelector(selectSummary)
  const portfolioStatus = useSelector(selectPortfolioStatus)

  const range = useSelector(selectRange)
  const analytics = useSelector(selectAnalytics)
  const analyticsStatus = useSelector(selectAnalyticsStatus)
  const series = useSelector(selectSeries)
  const chargeComponents = useSelector(selectChargeComponents)
  const byStock = useSelector(selectByStock)
  const recentClosed = useSelector(selectRecentClosedTrades)

  useEffect(() => {
    dispatch(fetchAnalytics(range))
  }, [dispatch, range])

  if (portfolioStatus === 'loading' && !summary) return <Loading label="Loading your portfolio" />

  if (holdings.length === 0 && !analytics?.trade_count) {
    return (
      <Empty
        title="Nothing recorded yet"
        hint="Record your first trade, or add an opening balance for shares you already owned. Charges are computed for you — you never type one."
        action={
          <button className="btn btn-primary" style={{ marginTop: 8 }} onClick={() => navigate('/add')}>
            <Icon name="plus" size={15} color="#06201c" />
            Add your first transaction
          </button>
        }
      />
    )
  }

  const rangeLabel = analytics
    ? `${shortDate(analytics.from)} — ${shortDate(analytics.to)}`
    : ''
  const hasClosedTrades = (analytics?.closed_trade_count ?? 0) > 0

  return (
    <div className="col" style={{ gap: 20 }}>
      {/* ---------- lifetime position ---------- */}
      <section className="col" style={{ gap: 12 }}>
        <span className="label">Where you stand today</span>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 320px) repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          <StatTile big label="Portfolio value" value={money(summary?.market_value)}
            sub={`invested ${money(summary?.invested)} · XIRR ${pct(summary?.xirr_pct)}`} />
          <StatTile label="Total P&L" value={signed(summary?.total_pnl)} tone={toneOf(summary?.total_pnl)}
            sub={`${pct(summary?.return_pct)} on invested`} />
          <StatTile label="Unrealized" value={signed(summary?.unrealized_pnl)} tone={toneOf(summary?.unrealized_pnl)}
            sub={`${summary?.holdings_count ?? 0} open holdings`} />
          <StatTile label="Realized (lifetime)" value={signed(summary?.realized_pnl)} tone={toneOf(summary?.realized_pnl)}
            sub="booked, kept separate" />
          <StatTile label="Charges (lifetime)" value={money(summary?.total_charges_paid)} tone="warn"
            sub="every fee your broker billed" />
        </div>
      </section>

      {/* ---------- period analysis ---------- */}
      <section className="col" style={{ gap: 12 }}>
        <div className="row" style={{ alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
          <div className="col" style={{ gap: 3 }}>
            <span className="label">What you earned in a period</span>
            <span className="faint" style={{ fontSize: 12 }}>
              {rangeLabel} · booked profit from trades you actually closed
            </span>
          </div>
          <div className="grow" />
          <DateRangePicker />
        </div>

        {analyticsStatus === 'failed' && <ErrorNote>Could not load the analysis for that range.</ErrorNote>}

        {analyticsStatus === 'loading' && !analytics ? (
          <Loading label="Crunching the period" />
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
              <StatTile label="Realized in period" value={signed(analytics?.realized_pnl)}
                tone={toneOf(analytics?.realized_pnl)}
                sub={`${analytics?.closed_trade_count ?? 0} closed trades`} />
              <StatTile label="Charges in period" value={money(analytics?.charges_paid)} tone="warn"
                sub={`${analytics?.trade_count ?? 0} trades placed`} />
              <StatTile label="Win rate" value={`${analytics?.win_rate ?? '0.0'}%`}
                tone={Number(analytics?.win_rate) >= 50 ? 'gain' : 'muted'}
                sub={`${analytics?.win_count ?? 0} up · ${analytics?.loss_count ?? 0} down`} />
              <StatTile label="Bought" value={money(analytics?.buy_turnover)} tone="muted"
                sub={`${analytics?.buy_count ?? 0} buy orders`} />
              <StatTile label="Sold" value={money(analytics?.sell_turnover)} tone="muted"
                sub={`${analytics?.sell_count ?? 0} sell orders`} />
            </div>

            {!hasClosedTrades ? (
              <div className="card" style={{ padding: 26 }}>
                <p className="faint" style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6 }}>
                  No positions were closed in this window, so there is no booked profit to chart.
                  Widen the range, or check <span className="accent">Total P&L</span> above — that
                  includes what your open holdings are worth right now.
                </p>
              </div>
            ) : (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 12 }}>
                  <ChartFrame
                    title="Cumulative realized P&L"
                    hint="running total of booked profit"
                    height={230}
                  >
                    <CumulativePnlChart data={series} />
                  </ChartFrame>

                  <ChartFrame
                    title={`Realized per ${analytics.granularity}`}
                    hint="green up, red down"
                    height={230}
                  >
                    <PeriodPnlChart data={series} />
                  </ChartFrame>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 12 }}>
                  <ChartFrame title="Realized by stock" hint="click a bar to open it">
                    <RealizedByStockChart
                      data={byStock.slice(0, 6)}
                      onSelect={(id) => id && navigate(`/portfolio/${id}`)}
                    />
                  </ChartFrame>

                  <ChartFrame
                    title="What the charges were"
                    hint={`${money(analytics.charges_paid)} in this period`}
                  >
                    <ChargeBreakdownChart data={chargeComponents} />
                  </ChartFrame>
                </div>

                {(analytics.best_trade || analytics.worst_trade) && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
                    {analytics.best_trade && (
                      <TradeHighlight label="Best closed trade" trade={analytics.best_trade} tone="gain" />
                    )}
                    {analytics.worst_trade && (
                      <TradeHighlight label="Worst closed trade" trade={analytics.worst_trade} tone="loss" />
                    )}
                  </div>
                )}
              </>
            )}

            {/* ---------- recent closed trades, five at a time ---------- */}
            {hasClosedTrades && (
              <div className="card" style={{ overflow: 'hidden' }}>
                <div className="row" style={{ padding: '13px 16px', borderBottom: '1px solid var(--line)' }}>
                  <span className="label">Recently closed · showing 5</span>
                  <div className="grow" />
                  <button className="accent" style={{ fontSize: 11.5 }} onClick={() => navigate('/transactions')}>
                    See the full ledger
                  </button>
                </div>
                <div className="scroll-x">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th><th style={{ textAlign: 'left' }}>Stock</th>
                        <th>Qty</th><th>Sold at</th><th>Charges</th>
                        <th>Held</th><th style={{ textAlign: 'center' }}>Term</th><th>Realized</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentClosed.map((t) => (
                        <tr key={t.id} className="clickable" onClick={() => navigate(`/portfolio/${t.stock}`)}>
                          <td className="muted">{shortDate(t.trade_date)}</td>
                          <td style={{ textAlign: 'left', fontWeight: 500 }}>{t.symbol}</td>
                          <td>{qty(t.quantity)}</td>
                          <td>{money(t.price)}</td>
                          <td className="warn">{money(t.charges)}</td>
                          <td className="muted">{t.holding_days}d</td>
                          <td style={{ textAlign: 'center' }}>
                            <span className={`pill ${t.term === 'LONG' ? 'pill-long' : 'pill-short'}`}>{t.term}</span>
                          </td>
                          <td className={toneOf(t.realized)}>{signed(t.realized)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </section>

      {/* ---------- holdings ---------- */}
      {holdings.length > 0 && (
        <section className="col" style={{ gap: 12 }}>
          <div className="card" style={{ overflow: 'hidden' }}>
            <div className="row" style={{ padding: '13px 16px', borderBottom: '1px solid var(--line)' }}>
              <span className="label">Open holdings · {holdings.length}</span>
              <div className="grow" />
              <button className="accent" style={{ fontSize: 11.5 }} onClick={() => navigate('/portfolio')}>
                Open portfolio
              </button>
            </div>
            <div className="scroll-x">
              <table>
                <thead>
                  <tr>
                    <th>Stock</th><th>Qty</th><th>Avg cost</th>
                    <th style={{ color: 'var(--accent)' }}>Break-even</th>
                    <th>LTP</th><th>Unrealized</th><th style={{ textAlign: 'left' }}>vs break-even</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.slice(0, 5).map((h) => (
                    <tr key={h.stock} className="clickable" onClick={() => navigate(`/portfolio/${h.stock}`)}>
                      <td style={{ fontWeight: 500 }}>{h.symbol}</td>
                      <td>{qty(h.quantity)}</td>
                      <td className="muted">{money(h.average_cost)}</td>
                      <td className="accent">{money(h.break_even)}</td>
                      <td>{h.has_price ? money(h.current_price) : <span className="warn">not set</span>}</td>
                      <td className={toneOf(h.unrealized_pnl)}>{signed(h.unrealized_pnl)}</td>
                      <td style={{ textAlign: 'left' }}>
                        <div className="row" style={{ gap: 10 }}>
                          <BreakEvenBar compact averageCost={h.average_cost} breakEven={h.break_even} currentPrice={h.current_price} />
                          <span className={toneOf(h.vs_break_even_pct)} style={{ fontSize: 11 }}>
                            {pct(h.vs_break_even_pct)}
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {holdings.length > 5 && (
              <div className="row" style={{ padding: '11px 16px', borderTop: '1px solid var(--line-soft)' }}>
                <span className="faint" style={{ fontSize: 11.5 }}>
                  {holdings.length - 5} more in the portfolio
                </span>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  )
}

function TradeHighlight({ label, trade, tone }) {
  return (
    <div className="card col" style={{ padding: '13px 15px', gap: 8 }}>
      <span className="label">{label}</span>
      <div className="row" style={{ alignItems: 'baseline', gap: 10 }}>
        <span className="mono" style={{ fontSize: 14, fontWeight: 600 }}>{trade.symbol}</span>
        <span className="mono faint" style={{ fontSize: 11 }}>
          {qty(trade.quantity)} @ {money(trade.price)} · {shortDate(trade.trade_date)}
        </span>
        <div className="grow" />
        <span className={`mono ${tone}`} style={{ fontSize: 15, fontWeight: 600 }}>
          {signed(trade.realized)}
        </span>
      </div>
      <span className="faint" style={{ fontSize: 11 }}>
        held {trade.holding_days} days · {trade.term.toLowerCase()}-term · {money(trade.charges)} in charges
      </span>
    </div>
  )
}
