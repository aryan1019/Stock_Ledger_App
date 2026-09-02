import { money } from '../utils/format'

/**
 * The position scale: loss zone, the amber band that IS the cost of exiting,
 * then profit. Average cost and break-even are deliberately two separate
 * markers — the gap between them is the whole point of the app.
 */
export default function BreakEvenBar({ averageCost, breakEven, currentPrice, recoveryBreakEven, compact = false }) {
  const avg = Number(averageCost)
  const be = Number(breakEven)
  const now = Number(currentPrice)
  if (!avg || !be) return null

  const lo = Math.min(avg, be, now) * 0.97
  const hi = Math.max(avg, be, now) * 1.03
  const span = hi - lo || 1
  const at = (v) => Math.max(0, Math.min(100, ((v - lo) / span) * 100))

  const avgPct = at(avg)
  const bePct = at(be)
  const nowPct = at(now)
  const inProfit = now >= be

  if (compact) {
    return (
      <div style={{ position: 'relative', height: 8, minWidth: 90 }}>
        <div style={{ position: 'absolute', inset: '1px 0', display: 'flex', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ width: `${avgPct}%`, background: 'var(--loss-bg)' }} />
          <div style={{ width: `${Math.max(bePct - avgPct, 1)}%`, background: 'var(--warn)' }} />
          <div style={{ width: `${100 - bePct}%`, background: 'var(--gain-bg)' }} />
        </div>
        <div
          title={`Current ${money(now)}`}
          style={{
            position: 'absolute', left: `${nowPct}%`, top: -1, width: 2.5, height: 10,
            background: inProfit ? 'var(--gain)' : 'var(--loss)',
          }}
        />
      </div>
    )
  }

  return (
    <div className="card" style={{ padding: '14px 18px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="row" style={{ alignItems: 'baseline' }}>
        <span className="label">Position scale</span>
        <span className="faint" style={{ fontSize: 11.5 }}>
          The amber band is what it costs to exit — ₹{money(be - avg)} per share.
        </span>
        <div className="grow" />
        {recoveryBreakEven && Number(recoveryBreakEven) > be && (
          <span className="mono faint" style={{ fontSize: 10.5 }}>
            RECOVERY BE <span className="warn">{money(recoveryBreakEven)}</span>
          </span>
        )}
      </div>

      <div style={{ position: 'relative', height: 54 }}>
        <div style={{ position: 'absolute', top: 20, left: 0, right: 0, height: 9, borderRadius: 2, display: 'flex', overflow: 'hidden' }}>
          <div style={{ width: `${avgPct}%`, background: 'var(--loss-bg)' }} />
          <div style={{ width: `${Math.max(bePct - avgPct, 0.6)}%`, background: 'var(--warn)' }} />
          <div style={{ width: `${100 - bePct}%`, background: 'var(--gain-bg)' }} />
        </div>

        <div style={{ position: 'absolute', left: `${avgPct}%`, top: 14, width: 2, height: 21, background: 'var(--text-2)' }} />
        <div className="mono muted" style={{ position: 'absolute', left: `${avgPct}%`, top: 0, transform: 'translateX(-50%)', fontSize: 10, whiteSpace: 'nowrap' }}>
          AVG {money(avg)}
        </div>

        <div style={{ position: 'absolute', left: `${bePct}%`, top: 14, width: 2, height: 21, background: 'var(--accent)' }} />
        <div className="mono accent" style={{ position: 'absolute', left: `${bePct}%`, top: 39, transform: 'translateX(-30%)', fontSize: 10, whiteSpace: 'nowrap' }}>
          BREAK-EVEN {money(be)}
        </div>

        <div style={{ position: 'absolute', left: `${nowPct}%`, top: 12, width: 3, height: 25, background: inProfit ? 'var(--gain)' : 'var(--loss)' }} />
        <div
          className={`mono ${inProfit ? 'gain' : 'loss'}`}
          style={{ position: 'absolute', left: `${nowPct}%`, top: 0, transform: 'translateX(-50%)', fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap' }}
        >
          NOW {money(now)}
        </div>
      </div>
    </div>
  )
}
