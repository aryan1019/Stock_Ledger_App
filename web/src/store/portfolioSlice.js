import {
  createAsyncThunk,
  createEntityAdapter,
  createSelector,
  createSlice,
} from '@reduxjs/toolkit'

import api, { apiError } from '../api/client'

/**
 * Holdings are stored normalised via createEntityAdapter, keyed by stock id,
 * so a row updated after a trade does not re-render the whole table.
 */
const holdingsAdapter = createEntityAdapter({
  selectId: (h) => h.stock,
  sortComparer: (a, b) => Number(b.total_pnl) - Number(a.total_pnl),
})

export const fetchPortfolio = createAsyncThunk(
  'portfolio/fetch',
  async (_, { rejectWithValue }) => {
    try {
      const { data } = await api.get('/portfolio/')
      return data
    } catch (e) {
      return rejectWithValue(apiError(e))
    }
  },
)

export const fetchSummary = createAsyncThunk(
  'portfolio/summary',
  async (_, { rejectWithValue }) => {
    try {
      const { data } = await api.get('/portfolio/summary/')
      return data
    } catch (e) {
      return rejectWithValue(apiError(e))
    }
  },
)

export const fetchStockDetail = createAsyncThunk(
  'portfolio/detail',
  async (stockId, { rejectWithValue }) => {
    try {
      const { data } = await api.get(`/portfolio/${stockId}/`)
      return data
    } catch (e) {
      return rejectWithValue(apiError(e, 'No transactions recorded for this stock yet.'))
    }
  },
)

export const setPrice = createAsyncThunk(
  'portfolio/setPrice',
  async ({ stockId, price }, { dispatch, rejectWithValue }) => {
    try {
      const { data } = await api.put(`/prices/${stockId}/`, { price })
      dispatch(fetchPortfolio())
      dispatch(fetchSummary())
      return data
    } catch (e) {
      return rejectWithValue(apiError(e))
    }
  },
)

const initialState = holdingsAdapter.getInitialState({
  status: 'idle',
  summary: null,
  detail: null,
  detailStatus: 'idle',
  error: null,
  filter: 'ALL', // ALL | PROFIT | BELOW_BE
})

const portfolioSlice = createSlice({
  name: 'portfolio',
  initialState,
  reducers: {
    setFilter(state, action) {
      state.filter = action.payload
    },
    clearDetail(state) {
      state.detail = null
      state.detailStatus = 'idle'
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchPortfolio.pending, (s) => {
        s.status = 'loading'
      })
      .addCase(fetchPortfolio.fulfilled, (s, a) => {
        holdingsAdapter.setAll(s, a.payload)
        s.status = 'succeeded'
        s.error = null
      })
      .addCase(fetchPortfolio.rejected, (s, a) => {
        s.status = 'failed'
        s.error = a.payload
      })
      .addCase(fetchSummary.fulfilled, (s, a) => {
        s.summary = a.payload
      })
      .addCase(fetchStockDetail.pending, (s) => {
        s.detailStatus = 'loading'
      })
      .addCase(fetchStockDetail.fulfilled, (s, a) => {
        s.detail = a.payload
        s.detailStatus = 'succeeded'
      })
      .addCase(fetchStockDetail.rejected, (s, a) => {
        s.detailStatus = 'failed'
        s.detail = null
        s.error = a.payload
      })
  },
})

export const { setFilter, clearDetail } = portfolioSlice.actions

export const {
  selectAll: selectAllHoldings,
  selectById: selectHoldingByStock,
  selectTotal: selectHoldingCount,
} = holdingsAdapter.getSelectors((s) => s.portfolio)

export const selectSummary = (s) => s.portfolio.summary
export const selectPortfolioStatus = (s) => s.portfolio.status
export const selectDetail = (s) => s.portfolio.detail
export const selectDetailStatus = (s) => s.portfolio.detailStatus
export const selectFilter = (s) => s.portfolio.filter

/** Memoised: only recomputes when holdings or the filter actually change. */
export const selectVisibleHoldings = createSelector(
  [selectAllHoldings, selectFilter],
  (holdings, filter) => {
    if (filter === 'PROFIT') return holdings.filter((h) => Number(h.unrealized_pnl) > 0)
    if (filter === 'BELOW_BE')
      return holdings.filter((h) => Number(h.current_price) < Number(h.break_even))
    return holdings
  },
)

export const selectFilterCounts = createSelector([selectAllHoldings], (holdings) => ({
  ALL: holdings.length,
  PROFIT: holdings.filter((h) => Number(h.unrealized_pnl) > 0).length,
  BELOW_BE: holdings.filter((h) => Number(h.current_price) < Number(h.break_even)).length,
}))

export const selectStalePriceCount = createSelector(
  [selectAllHoldings],
  (holdings) => holdings.filter((h) => !h.has_price).length,
)

export default portfolioSlice.reducer
