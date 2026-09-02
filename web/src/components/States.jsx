export function Loading({ label = 'Loading' }) {
  return (
    <div className="row" style={{ padding: 32, justifyContent: 'center', gap: 12 }}>
      <div className="spinner" />
      <span className="faint" style={{ fontSize: 13 }}>{label}…</span>
    </div>
  )
}

export function Empty({ title, hint, action }) {
  return (
    <div className="card col" style={{ padding: 40, alignItems: 'center', gap: 10, textAlign: 'center' }}>
      <span style={{ fontSize: 15, fontWeight: 600 }}>{title}</span>
      {hint && <span className="faint" style={{ fontSize: 13, maxWidth: 460, lineHeight: 1.55 }}>{hint}</span>}
      {action}
    </div>
  )
}

export function ErrorNote({ children }) {
  if (!children) return null
  return (
    <div
      className="row"
      style={{
        background: 'var(--loss-bg)',
        border: '1px solid #4a2620',
        borderRadius: 'var(--r)',
        padding: '11px 14px',
        color: 'var(--loss)',
        fontSize: 13,
        lineHeight: 1.5,
      }}
    >
      {children}
    </div>
  )
}
