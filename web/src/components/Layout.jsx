import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { logout, selectUser } from '../store/authSlice'
import { fetchPlans, fetchStocks } from '../store/referenceSlice'
import {
  fetchPortfolio,
  fetchSummary,
  selectStalePriceCount,
} from '../store/portfolioSlice'
import Icon from './Icon'

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/portfolio', label: 'Portfolio' },
  { to: '/transactions', label: 'Ledger' },
  { to: '/settings', label: 'Settings' },
]

export default function Layout() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const user = useSelector(selectUser)
  const stalePrices = useSelector(selectStalePriceCount)

  useEffect(() => {
    dispatch(fetchPortfolio())
    dispatch(fetchSummary())
    dispatch(fetchStocks())
    dispatch(fetchPlans())
  }, [dispatch])

  const initials = (user?.name || user?.email || '?').slice(0, 2).toUpperCase()

  return (
    <div style={{ minHeight: '100%', display: 'flex', flexDirection: 'column' }}>
      <header
        style={{
          height: 52,
          flexShrink: 0,
          borderBottom: '1px solid var(--line)',
          background: 'var(--raised)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 20px',
          gap: 28,
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <div className="row" style={{ gap: 9 }}>
          <Icon name="logo" size={18} color="var(--accent)" />
          <span className="mono" style={{ fontSize: 13, fontWeight: 600, letterSpacing: '.06em' }}>
            LEDGER
          </span>
        </div>

        <nav className="row" style={{ gap: 2 }}>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              style={({ isActive }) => ({
                padding: '6px 12px',
                fontSize: 12.5,
                borderRadius: 4,
                color: isActive ? 'var(--text)' : 'var(--text-2)',
                background: isActive ? 'var(--surface-3)' : 'transparent',
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="grow" />

        {stalePrices > 0 && (
          <div
            className="mono"
            style={{
              fontSize: 10.5,
              color: 'var(--warn)',
              border: '1px solid var(--warn-line)',
              background: 'var(--warn-bg)',
              borderRadius: 4,
              padding: '5px 9px',
            }}
          >
            {stalePrices} {stalePrices === 1 ? 'PRICE' : 'PRICES'} NOT SET
          </div>
        )}

        <button className="btn btn-primary" style={{ height: 34 }} onClick={() => navigate('/add')}>
          <Icon name="plus" size={15} color="#06201c" />
          Add transaction
        </button>

        <div className="row" style={{ gap: 8 }}>
          <div
            className="mono muted"
            title={user?.email}
            style={{
              width: 26, height: 26, borderRadius: 4, background: 'var(--surface-3)',
              border: '1px solid var(--line)', display: 'flex', alignItems: 'center',
              justifyContent: 'center', fontSize: 11,
            }}
          >
            {initials}
          </div>
          <button
            className="faint"
            style={{ fontSize: 12 }}
            onClick={() => dispatch(logout()).then(() => navigate('/login'))}
          >
            Sign out
          </button>
        </div>
      </header>

      <main style={{ flexGrow: 1, padding: '22px 24px 60px', maxWidth: 1560, width: '100%', margin: '0 auto' }}>
        <Outlet />
      </main>
    </div>
  )
}
