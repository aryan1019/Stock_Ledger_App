export default function StatTile({ label, value, sub, tone = 'default', big = false }) {
  const colors = {
    default: 'var(--text)',
    gain: 'var(--gain)',
    loss: 'var(--loss)',
    warn: 'var(--warn)',
    accent: 'var(--accent)',
    muted: 'var(--text-2)',
  }
  return (
    <div
      className="card"
      style={{
        padding: '13px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 7,
        background: tone === 'warn' ? 'var(--warn-bg)' : 'var(--surface)',
        borderColor: tone === 'warn' ? 'var(--warn-line)' : 'var(--line)',
      }}
    >
      <span className="label" style={{ color: tone === 'warn' ? 'var(--warn)' : 'var(--text-3)' }}>
        {label}
      </span>
      <span
        className="num"
        style={{
          fontFamily: 'var(--cond)',
          fontSize: big ? 34 : 24,
          fontWeight: 600,
          lineHeight: 1.05,
          color: colors[tone] ?? colors.default,
        }}
      >
        {value}
      </span>
      {sub && <span className="mono faint" style={{ fontSize: 11 }}>{sub}</span>}
    </div>
  )
}
