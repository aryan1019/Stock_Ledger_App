import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'

import Icon from '../components/Icon'
import { Loading } from '../components/States'
import api from '../api/client'
import { selectUser, setBrokerPlan } from '../store/authSlice'
import { fetchPlans, selectAllPlans } from '../store/referenceSlice'
import { money } from '../utils/format'

/**
 * One reference trade, priced under every plan, so the comparison is like for
 * like. This is a PROBE — it is not used in any of your real figures. Your own
 * trades are costed with whichever plan is selected below.
 */
const SAMPLE = { quantity: '5', price: '3899', exchange: 'NSE' }
const SAMPLE_TURNOVER = '19,495'

export default function Settings() {
  const dispatch = useDispatch()
  const user = useSelector(selectUser)
  const plans = useSelector(selectAllPlans)
  const [costs, setCosts] = useState({})
  const [saving, setSaving] = useState(null)

  useEffect(() => {
    dispatch(fetchPlans())
  }, [dispatch])

  // Price the same trade under each plan — buy AND sell, because the DP charge
  // only ever appears on a sell and that is where plans differ most.
  useEffect(() => {
    let cancelled = false
    async function price() {
      const stocks = await api.get('/stocks/')
      const stock = stocks.data[0]
      if (!stock) return
      const entries = await Promise.all(
        plans.map(async (p) => {
          try {
            const [buy, sell] = await Promise.all([
              api.post('/transactions/preview/', { ...SAMPLE, type: 'BUY', stock: stock.id, broker_plan: p.id }),
              api.post('/transactions/preview/', { ...SAMPLE, type: 'SELL', stock: stock.id, broker_plan: p.id }),
            ])
            return [p.id, { buy: buy.data.total_charges, sell: sell.data.total_charges }]
          } catch {
            return [p.id, null]
          }
        }),
      )
      if (!cancelled) setCosts(Object.fromEntries(entries))
    }
    if (plans.length) price()
    return () => { cancelled = true }
  }, [plans])

  const sorted = useMemo(
    () =>
      [...plans].sort(
        (a, b) => Number(costs[a.id]?.buy ?? 1e9) - Number(costs[b.id]?.buy ?? 1e9),
      ),
    [plans, costs],
  )

  const choose = async (planId) => {
    setSaving(planId)
    await dispatch(setBrokerPlan(planId))
    setSaving(null)
  }

  if (!plans.length) return <Loading label="Loading broker plans" />

  const active = plans.find((p) => p.id === user?.default_broker_plan)

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(320px, 450px)', gap: 24, alignItems: 'start' }}>
      <div className="col" style={{ gap: 14 }}>
        <div className="col" style={{ gap: 5 }}>
          <h1 style={{ margin: 0, fontSize: 19, fontWeight: 600 }}>Broker &amp; charges</h1>
          <span className="faint" style={{ fontSize: 12.5, lineHeight: 1.55, maxWidth: '62ch' }}>
            Pick the plan you actually trade on. Every transaction you record is then costed with
            it automatically — you never type a charge.
          </span>
        </div>

        {/* What the number in the right-hand column actually is. */}
        <div className="card row" style={{ padding: '12px 14px', gap: 11, alignItems: 'flex-start' }}>
          <Icon name="info" size={15} color="var(--accent)" />
          <p className="faint" style={{ margin: 0, fontSize: 12, lineHeight: 1.55 }}>
            The two figures on the right are a <span className="accent">comparison probe</span>, not
            your money: the same sample trade — 5 shares at ₹3,899, turnover ₹{SAMPLE_TURNOVER} — priced
            under each plan so you can see what they cost relative to one another. Sell is shown
            separately because the DP charge only ever lands on a sell, and that is where plans
            differ most.
          </p>
        </div>

        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span className="label">Your plan</span>
          <span className="label">Sample ₹{SAMPLE_TURNOVER} · buy / sell</span>
        </div>

        <div className="col" style={{ gap: 8 }}>
          {sorted.map((p) => {
            const on = p.id === user?.default_broker_plan
            const warns = /NOT the zero-brokerage/i.test(p.notes || '')
            const cost = costs[p.id]
            return (
              <button
                key={p.id}
                onClick={() => choose(p.id)}
                style={{
                  border: `${on ? 1.5 : 1}px solid ${on ? 'var(--accent)' : warns ? 'var(--warn-line)' : 'var(--line)'}`,
                  background: on ? 'var(--accent-dim)' : warns ? 'var(--warn-bg)' : 'var(--surface)',
                  borderRadius: 7, padding: '14px 16px', display: 'flex',
                  alignItems: 'flex-start', gap: 13, textAlign: 'left', width: '100%',
                }}
              >
                <span
                  style={{
                    width: 17, height: 17, borderRadius: '50%', flexShrink: 0, marginTop: 2,
                    border: `1.5px solid ${on ? 'var(--accent)' : '#3a434f'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                >
                  {on && <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)' }} />}
                </span>

                <span className="col grow" style={{ gap: 4 }}>
                  <span className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 14, fontWeight: on ? 600 : 500 }}>{p.display_name}</span>
                    {on && (
                      <span className="mono accent" style={{ fontSize: 9.5, border: '1px solid var(--accent-line)', borderRadius: 3, padding: '2px 6px' }}>
                        IN USE
                      </span>
                    )}
                    {p.verified ? (
                      <span className="mono gain" style={{ fontSize: 9.5, background: 'var(--gain-bg)', borderRadius: 3, padding: '2px 6px' }}>
                        ✓ MATCHED TO A REAL BILL
                      </span>
                    ) : (
                      <span className="mono faint" style={{ fontSize: 9.5, border: '1px solid var(--line)', borderRadius: 3, padding: '2px 6px' }}>
                        FROM PUBLISHED RATES
                      </span>
                    )}
                  </span>
                  <span style={{ fontSize: 12, color: warns ? 'var(--warn)' : 'var(--text-2)', lineHeight: 1.45 }}>
                    {p.notes}
                  </span>
                </span>

                <span className="col" style={{ gap: 3, alignItems: 'flex-end', minWidth: 96 }}>
                  {saving === p.id ? (
                    <span className="spinner" />
                  ) : cost ? (
                    <>
                      <span className={`mono ${on ? 'accent' : warns ? 'warn' : 'muted'}`} style={{ fontSize: 14 }}>
                        {money(cost.buy)}
                      </span>
                      <span className="mono faint" style={{ fontSize: 11 }}>
                        sell {money(cost.sell)}
                      </span>
                    </>
                  ) : (
                    <span className="mono faint" style={{ fontSize: 14 }}>—</span>
                  )}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* ---------------- component detail ---------------- */}
      <div className="col" style={{ gap: 12 }}>
        <span className="label">What {active?.display_name || 'this plan'} charges</span>

        <div className="card scroll-x" style={{ overflow: 'hidden' }}>
          <table>
            <thead>
              <tr><th style={{ textAlign: 'left' }}>Component</th><th>Rate</th><th style={{ textAlign: 'center' }}>Side</th></tr>
            </thead>
            <tbody>
              {(active?.components || []).map((c) => (
                <tr key={c.code}>
                  <td style={{ textAlign: 'left' }} className="muted">{c.label}</td>
                  <td style={{ fontSize: 11.5 }}>{describeRate(c)}</td>
                  <td style={{ textAlign: 'center', fontSize: 10 }}
                      className={c.side === 'BUY' ? 'gain' : c.side === 'SELL' ? 'loss' : 'faint'}>
                    {c.side}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!(active?.components || []).some((c) => c.code === 'DP') && (
          <div className="card row" style={{ padding: '12px 14px', gap: 11, alignItems: 'flex-start', borderColor: 'var(--accent-line)', background: 'var(--accent-dim)' }}>
            <Icon name="info" size={15} color="var(--accent)" />
            <p style={{ margin: 0, fontSize: 12, lineHeight: 1.55, color: '#7c9490' }}>
              This plan has <span className="accent">no DP charge</span>, so selling costs less than
              on plans that levy one. Most brokers charge ₹15–20 per scrip on any day you sell.
            </p>
          </div>
        )}

        <div className="card col" style={{ padding: '13px 15px', gap: 9, background: 'var(--warn-bg)', borderColor: 'var(--warn-line)' }}>
          <div className="row" style={{ gap: 9 }}>
            <Icon name="info" size={15} color="var(--warn)" />
            <span className="warn" style={{ fontSize: 12.5, fontWeight: 500 }}>
              {active?.verified ? 'Checked against your real bills' : 'From published rate cards'}
            </span>
          </div>
          <span style={{ fontSize: 11.5, color: '#7a6640', lineHeight: 1.55 }}>
            {active?.verified
              ? 'These rates reproduce two real charge breakdowns from your broker to the paisa. Rates are stored with effective dates, so changing one never rewrites trades you have already recorded.'
              : 'These come from the broker’s published rate card, not a bill you supplied. Compare a recent contract note and tell me if anything differs — the rates are data, so correcting one is a row change, not a code change.'}
          </span>
        </div>

        <div className="card col" style={{ padding: '13px 15px', gap: 6 }}>
          <span className="label">Account</span>
          <span className="mono muted" style={{ fontSize: 12.5 }}>{user?.email}</span>
        </div>
      </div>
    </div>
  )
}

function describeRate(c) {
  if (c.basis === 'PERCENT_OF') return `${(Number(c.rate) * 100).toFixed(0)}% of the above`
  if (c.basis === 'PERCENT_TURNOVER') {
    const base = `${(Number(c.rate) * 100).toFixed(5).replace(/0+$/, '').replace(/\.$/, '')}%`
    if (c.cap && c.floor) return `${base}, max ₹${c.cap}, min ₹${c.floor}`
    if (c.cap) return `lower of ₹${c.cap} or ${base}`
    return base
  }
  if (c.basis === 'FLAT_PER_SCRIP_PER_DAY') return `₹${c.amount} per scrip/day`
  if (c.basis === 'FLAT_PER_ORDER') return `₹${c.amount} flat`
  if (c.basis === 'PER_SHARE') return `₹${c.amount} per share`
  return '—'
}
