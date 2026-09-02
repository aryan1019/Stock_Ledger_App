/**
 * All money arrives from the API as strings so it never becomes a JS float.
 * These helpers format for display only — no arithmetic on prices anywhere
 * in the UI.
 */

const INR = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export const money = (v) => (v === null || v === undefined || v === '' ? '—' : INR.format(Number(v)))

export const signed = (v) => {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  return `${n > 0 ? '+' : n < 0 ? '−' : ''}${INR.format(Math.abs(n))}`
}

export const pct = (v) => {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  return `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(2)}%`
}

export const qty = (v) => {
  const n = Number(v ?? 0)
  return Number.isInteger(n) ? String(n) : n.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
}

export const toneOf = (v) => {
  const n = Number(v ?? 0)
  return n > 0 ? 'gain' : n < 0 ? 'loss' : 'muted'
}

export const shortDate = (iso) =>
  iso
    ? new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      })
    : '—'

export const today = () => new Date().toISOString().slice(0, 10)

export const daysAgoISO = (n) => {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}
