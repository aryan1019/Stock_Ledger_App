import { useSelector } from 'react-redux'
import { Navigate, useLocation } from 'react-router-dom'

import { selectAuthStatus } from '../store/authSlice'
import { Loading } from './States'

export default function ProtectedRoute({ children }) {
  const status = useSelector(selectAuthStatus)
  const location = useLocation()

  if (status === 'loading') return <Loading label="Restoring your session" />
  if (status !== 'authenticated') return <Navigate to="/login" state={{ from: location }} replace />
  return children
}
