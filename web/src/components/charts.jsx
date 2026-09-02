import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

import { money, signed } from '../utils/format'

/*
 * Chart conventions, applied consistently:
 *   - one y-axis, never two
 *   - grid and axes recessive; the data carries the ink
 *   - colour encodes SIGN (gain / loss), not series identity
 *   - charges use a single amber hue, because they are one measure
 *   - every chart has a hover layer; no value printed on every mark
 */

const AXIS = { stroke: 'var(--text-3)', fontSize: 10, fontFamily: 'var(--mono)' }
const GRID = 'var(--line-soft)'

const compact = (n) => {
  const abs = Math.abs(n)
  if (abs >= 1e7) return `${(n / 1e7).toFixed(1)}Cr`
  if (abs >= 1e5) return `${(n / 1e5).toFixed(1)}L`
  if (abs >= 1e3) return `${(n / 1e3).toFixed(0)}k`
  return String(Math.round(n))
}

const shortBucket = (b) =>
  b?.length === 7
    ? new Date(`${b}-01T00:00:00`).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
    : new Date(`${b}T00:00:00`).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })

function TipShell({ title, rows }) {
  return (
    <div
      style={{
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 6,
        padding: '9px 12px',
        boxShadow: '0 8px 24px -12px rgba(0,0,0,.8)',
      }}
    >
      <div className="mono faint" style={{ fontSize: 10, marginBottom: 6 }}>{title}</div>
      {rows.map(([label, value, tone]) => (
        <div
          key={label}
          className="row mono"
          style={{ justifyContent: 'space-between', gap: 18, fontSize: 12 }}
        >
          <span className="muted">{label}</span>
          <span className={tone || ''}>{value}</span>
        </div>
      ))}
    </div>
  )
}

export function ChartFrame({ title, hint, height = 220, children }) {
  return (
    <div className="card col" style={{ padding: '14px 16px 10px', gap: 4 }}>
      <div className="row" style={{ alignItems: 'baseline', gap: 10 }}>
        <span className="label">{title}</span>
        {hint && <span className="faint" style={{ fontSize: 11 }}>{hint}</span>}
      </div>
      <div style={{ width: '100%', height }}>{children}</div>
    </div>
  )
}

/* ---------------------------------------------------------------- */

export function CumulativePnlChart({ data }) {
  const last = data.length ? data[data.length - 1].cumulative : 0
  const positive = last >= 0
  const stroke = positive ? 'var(--gain)' : 'var(--loss)'

  return (
    <ResponsiveContainer>
      <AreaChart data={data} margin={{ top: 6, right: 8, left: -12, bottom: 0 }}>
        <defs>
          <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
            <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="bucket" tickFormatter={shortBucket} tickLine={false} axisLine={false} {...AXIS} minTickGap={26} />
        <YAxis tickFormatter={compact} tickLine={false} axisLine={false} width={52} {...AXIS} />
        <ReferenceLine y={0} stroke="var(--text-3)" strokeDasharray="3 3" />
        <Tooltip
          cursor={{ stroke: 'var(--text-3)', strokeDasharray: '3 3' }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TipShell
                title={shortBucket(label)}
                rows={[
                  ['Cumulative', signed(payload[0].payload.cumulative),
                    payload[0].payload.cumulative >= 0 ? 'gain' : 'loss'],
                  ['That period', signed(payload[0].payload.realized),
                    payload[0].payload.realized >= 0 ? 'gain' : 'loss'],
                ]}
              />
            ) : null
          }
        />
        <Area
          type="monotone" dataKey="cumulative" stroke={stroke} strokeWidth={2}
          fill="url(#pnlFill)" dot={false}
          activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

/* ---------------------------------------------------------------- */

export function PeriodPnlChart({ data }) {
  return (
    <ResponsiveContainer>
      <BarChart data={data} margin={{ top: 6, right: 8, left: -12, bottom: 0 }} barCategoryGap="26%">
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="bucket" tickFormatter={shortBucket} tickLine={false} axisLine={false} {...AXIS} minTickGap={26} />
        <YAxis tickFormatter={compact} tickLine={false} axisLine={false} width={52} {...AXIS} />
        <ReferenceLine y={0} stroke="var(--text-3)" />
        <Tooltip
          cursor={{ fill: 'var(--surface-3)', fillOpacity: 0.4 }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TipShell
                title={shortBucket(label)}
                rows={[
                  ['Realized', signed(payload[0].payload.realized),
                    payload[0].payload.realized >= 0 ? 'gain' : 'loss'],
                  ['Charges', money(payload[0].payload.charges), 'warn'],
                ]}
              />
            ) : null
          }
        />
        <Bar dataKey="realized" radius={[3, 3, 0, 0]} isAnimationActive={false}>
          {data.map((d) => (
            <Cell
              key={d.bucket}
              fill={d.realized >= 0 ? 'var(--gain)' : 'var(--loss)'}
              fillOpacity={0.85}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ---------------------------------------------------------------- */

const CHARGE_LABELS = {
  STT: 'Securities Transaction Tax',
  DP: 'DP charge',
  STAMP: 'Stamp duty',
  EXCH_TXN: 'Exchange txn charge',
  SEBI: 'SEBI turnover fee',
  GST: 'GST',
  BROKERAGE: 'Brokerage',
  MANUAL: 'Manually entered',
}

/** One measure across components, so one hue stepped by magnitude — not a rainbow. */
export function ChargeBreakdownChart({ data, height = 190 }) {
  const max = Math.max(...data.map((d) => d.amount), 1)
  const rows = data.map((d) => ({ ...d, label: CHARGE_LABELS[d.code] || d.code }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} layout="vertical" margin={{ top: 2, right: 46, left: 4, bottom: 2 }} barCategoryGap="22%">
        <XAxis type="number" hide domain={[0, max * 1.12]} />
        <YAxis
          type="category" dataKey="code" width={94} tickLine={false} axisLine={false}
          {...AXIS} tickFormatter={(c) => CHARGE_LABELS[c]?.split(' ')[0] || c}
        />
        <Tooltip
          cursor={{ fill: 'var(--surface-3)', fillOpacity: 0.4 }}
          content={({ active, payload }) =>
            active && payload?.length ? (
              <TipShell
                title={payload[0].payload.label}
                rows={[['Paid in period', money(payload[0].payload.amount), 'warn']]}
              />
            ) : null
          }
        />
        <Bar dataKey="amount" radius={[0, 3, 3, 0]} isAnimationActive={false}>
          {rows.map((d) => (
            <Cell
              key={d.code}
              fill="var(--warn)"
              fillOpacity={0.35 + 0.6 * (d.amount / max)}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ---------------------------------------------------------------- */

export function RealizedByStockChart({ data, height = 190, onSelect }) {
  const max = Math.max(...data.map((d) => Math.abs(d.realized)), 1)

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 2, right: 12, left: 4, bottom: 2 }} barCategoryGap="22%">
        <XAxis type="number" hide domain={[-max * 1.12, max * 1.12]} />
        <YAxis type="category" dataKey="symbol" width={94} tickLine={false} axisLine={false} {...AXIS} />
        <ReferenceLine x={0} stroke="var(--text-3)" />
        <Tooltip
          cursor={{ fill: 'var(--surface-3)', fillOpacity: 0.4 }}
          content={({ active, payload }) =>
            active && payload?.length ? (
              <TipShell
                title={payload[0].payload.symbol}
                rows={[
                  ['Realized', signed(payload[0].payload.realized),
                    payload[0].payload.realized >= 0 ? 'gain' : 'loss'],
                  ['Closed trades', String(payload[0].payload.trades)],
                ]}
              />
            ) : null
          }
        />
        <Bar
          dataKey="realized" radius={3} isAnimationActive={false}
          onClick={(d) => onSelect?.(d.stock)}
          style={{ cursor: onSelect ? 'pointer' : 'default' }}
        >
          {data.map((d) => (
            <Cell
              key={d.symbol}
              fill={d.realized >= 0 ? 'var(--gain)' : 'var(--loss)'}
              fillOpacity={0.85}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
