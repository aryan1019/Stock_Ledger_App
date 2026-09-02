import { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useLocation, useNavigate } from 'react-router-dom'

import Icon from '../components/Icon'
import { ErrorNote } from '../components/States'
import {
  clearError, login, register, selectAuthError, selectAuthStatus,
} from '../store/authSlice'

export default function Login() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const location = useLocation()
  const status = useSelector(selectAuthStatus)
  const error = useSelector(selectAuthError)

  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ email: '', name: '', password: '' })

  useEffect(() => {
    if (status === 'authenticated') navigate(location.state?.from?.pathname || '/', { replace: true })
  }, [status, navigate, location])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = (e) => {
    e.preventDefault()
    dispatch(clearError())
    if (mode === 'login') dispatch(login({ email: form.email, password: form.password }))
    else dispatch(register(form))
  }

  const busy = status === 'loading'

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24 }}>
      <div style={{ width: '100%', maxWidth: 400, display: 'flex', flexDirection: 'column', gap: 26 }}>
        <div className="col" style={{ gap: 10 }}>
          <div className="row" style={{ gap: 10 }}>
            <Icon name="logo" size={22} color="var(--accent)" />
            <span className="mono" style={{ fontSize: 17, fontWeight: 600, letterSpacing: '.06em' }}>
              LEDGER
            </span>
          </div>
          <p className="faint" style={{ margin: 0, fontSize: 13, lineHeight: 1.55 }}>
            Your true cost per share, your real break-even, and every charge your broker
            actually bills — kept separate from realized profit.
          </p>
        </div>

        <form onSubmit={submit} className="card" style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 15 }}>
          <div className="row" style={{ gap: 2 }}>
            {['login', 'register'].map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => { setMode(m); dispatch(clearError()) }}
                style={{
                  padding: '7px 13px', fontSize: 12.5, borderRadius: 4,
                  color: mode === m ? 'var(--text)' : 'var(--text-3)',
                  background: mode === m ? 'var(--surface-3)' : 'transparent',
                }}
              >
                {m === 'login' ? 'Sign in' : 'Create account'}
              </button>
            ))}
          </div>

          <ErrorNote>{error}</ErrorNote>

          <label className="col" style={{ gap: 7 }}>
            <span className="label">Email</span>
            <input type="email" required autoComplete="email" value={form.email} onChange={set('email')} placeholder="you@example.com" />
          </label>

          {mode === 'register' && (
            <label className="col" style={{ gap: 7 }}>
              <span className="label">Name</span>
              <input type="text" value={form.name} onChange={set('name')} placeholder="Optional" />
            </label>
          )}

          <label className="col" style={{ gap: 7 }}>
            <span className="label">Password</span>
            <input
              type="password" required minLength={8}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              value={form.password} onChange={set('password')} placeholder="At least 8 characters"
            />
          </label>

          <button type="submit" className="btn btn-primary" style={{ height: 44 }} disabled={busy}>
            {busy ? <span className="spinner" /> : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  )
}
