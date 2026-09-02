import { createAsyncThunk, createSelector, createSlice } from '@reduxjs/toolkit'

import api, { apiError } from '../api/client'

export const PRESETS = [
  { key: '7D', label: '7 days' },
  { key: '30D', label: '30 days' },
  { key: '90D', label: '90 days' },
  { key: '1Y', label: '1 year' },
  { key: 'ALL', label: 'All time' },
]

export const fetchAnalytics = createAsyncThunk(
  'analytics/fetch',
  async (range, { rejectWithValue }) => {
    try {
      const params = range.custom ? { from: range.from, to: range.to } : { preset: range.preset }
      const { data } = await api.get('/portfolio/analytics/', { params })
      return data
    } catch (e) {
      return rejectWithValue(apiError(e))
    }
  },
)

const initialState = {
  data: null,
  status: 'idle',
  error: null,
  range: { preset: '90D', custom: false, from: '', to: '' },
}

const analyticsSlice = createSlice({
  name: 'analytics',
  initialState,
  reducers: {
    setPreset(state, action) {
      state.range = { preset: action.payload, custom: false, from: '', to: '' }
    },
    setCustomRange(state, action) {
      const { from, to } = action.payload
      state.range = { preset: null, custom: true, from, to }
    },
  },
  extraReducers: (b) => {
    b.addCase(fetchAnalytics.pending, (s) => {
      s.status = 'loading'
      s.error = null
    })
      .addCase(fetchAnalytics.fulfilled, (s, a) => {
        s.data = a.payload
        s.status = 'succeeded'
      })
      .addCase(fetchAnalytics.rejected, (s, a) => {
        s.status = 'failed'
        s.error = a.payload
      })
  },
})

export const { setPreset, setCustomRange } = analyticsSlice.actions

export const selectAnalytics = (s) => s.analytics.data
export const selectAnalyticsStatus = (s) => s.analytics.status
export const selectRange = (s) => s.analytics.range

/** Recharts wants numbers; the API sends strings. Convert once, memoised. */
export const selectSeries = createSelector([selectAnalytics], (data) =>
  (data?.series ?? []).map((pt) => ({
    bucket: pt.bucket,
    realized: Number(pt.realized),
    cumulative: Number(pt.cumulative),
    charges: Number(pt.charges),
  })),
)

export const selectChargeComponents = createSelector([selectAnalytics], (data) =>
  (data?.charge_components ?? []).map((c) => ({ code: c.code, amount: Number(c.amount) })),
)

export const selectByStock = createSelector([selectAnalytics], (data) =>
  (data?.by_stock ?? []).map((s) => ({
    symbol: s.symbol,
    stock: s.stock,
    realized: Number(s.realized),
    trades: s.trades,
  })),
)

/** The dashboard table shows five; the ledger shows the rest. */
export const selectRecentClosedTrades = createSelector([selectAnalytics], (data) =>
  (data?.closed_trades ?? []).slice(0, 5),
)

export const selectHasActivity = createSelector(
  [selectAnalytics],
  (data) => Boolean(data && data.trade_count > 0),
)

export default analyticsSlice.reducer
