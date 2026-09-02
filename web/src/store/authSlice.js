import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'

import api, { apiError, tokens } from '../api/client'

export const login = createAsyncThunk('auth/login', async (creds, { rejectWithValue }) => {
  try {
    const { data } = await api.post('/auth/login/', creds)
    tokens.set(data.access, data.refresh)
    const me = await api.get('/me/')
    return me.data
  } catch (e) {
    return rejectWithValue(apiError(e, 'Email or password is incorrect.'))
  }
})

export const register = createAsyncThunk('auth/register', async (body, { rejectWithValue }) => {
  try {
    const { data } = await api.post('/auth/register/', body)
    tokens.set(data.access, data.refresh)
    return data.user
  } catch (e) {
    return rejectWithValue(apiError(e, 'Could not create the account.'))
  }
})

export const loadMe = createAsyncThunk('auth/loadMe', async (_, { rejectWithValue }) => {
  try {
    const { data } = await api.get('/me/')
    return data
  } catch (e) {
    return rejectWithValue(apiError(e))
  }
})

export const setBrokerPlan = createAsyncThunk(
  'auth/setBrokerPlan',
  async (planId, { rejectWithValue }) => {
    try {
      const { data } = await api.patch('/me/', { default_broker_plan: planId })
      return data
    } catch (e) {
      return rejectWithValue(apiError(e))
    }
  },
)

export const logout = createAsyncThunk('auth/logout', async () => {
  try {
    await api.post('/auth/logout/', { refresh: tokens.refresh() })
  } catch {
    /* logging out locally is what matters */
  }
  tokens.clear()
})

const initialState = {
  user: null,
  status: tokens.access() ? 'loading' : 'idle',
  error: null,
}

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearError(state) {
      state.error = null
    },
    sessionExpired(state) {
      state.user = null
      state.status = 'idle'
      state.error = 'Your session expired. Please sign in again.'
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadMe.pending, (s) => {
        s.status = 'loading'
      })
      .addCase(loadMe.rejected, (s) => {
        s.status = 'idle'
        s.user = null
      })
      .addCase(logout.fulfilled, (s) => {
        s.user = null
        s.status = 'idle'
        s.error = null
      })
      .addMatcher(
        (a) => [login.pending.type, register.pending.type].includes(a.type),
        (s) => {
          s.status = 'loading'
          s.error = null
        },
      )
      .addMatcher(
        (a) =>
          [login.fulfilled.type, register.fulfilled.type, loadMe.fulfilled.type,
            setBrokerPlan.fulfilled.type].includes(a.type),
        (s, a) => {
          s.user = a.payload
          s.status = 'authenticated'
          s.error = null
        },
      )
      .addMatcher(
        (a) => [login.rejected.type, register.rejected.type].includes(a.type),
        (s, a) => {
          s.status = 'idle'
          s.error = a.payload
        },
      )
  },
})

export const { clearError, sessionExpired } = authSlice.actions
export const selectUser = (s) => s.auth.user
export const selectIsAuthenticated = (s) => s.auth.status === 'authenticated'
export const selectAuthStatus = (s) => s.auth.status
export const selectAuthError = (s) => s.auth.error

export default authSlice.reducer
