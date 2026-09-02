import { useEffect } from 'react'
import { useDispatch } from 'react-redux'
import { Navigate, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import { tokens } from './api/client'
import { loadMe } from './store/authSlice'
import AddTransaction from './screens/AddTransaction'
import Dashboard from './screens/Dashboard'
import Ledger from './screens/Ledger'
import Login from './screens/Login'
import PortfolioScreen from './screens/PortfolioScreen'
import Settings from './screens/Settings'
import StockDetail from './screens/StockDetail'

export default function App() {
  const dispatch = useDispatch()

  // A page refresh keeps the session: the token is on disk, so re-hydrate the user.
  useEffect(() => {
    if (tokens.access()) dispatch(loadMe())
  }, [dispatch])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/portfolio" element={<PortfolioScreen />} />
        <Route path="/portfolio/:stockId" element={<StockDetail />} />
        <Route path="/transactions" element={<Ledger />} />
        <Route path="/add" element={<AddTransaction />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
