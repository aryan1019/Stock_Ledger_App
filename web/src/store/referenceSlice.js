import { createAsyncThunk, createEntityAdapter, createSelector, createSlice } from '@reduxjs/toolkit'

import api, { apiError } from '../api/client'

const stocksAdapter = createEntityAdapter({
  sortComparer: (a, b) => a.symbol.localeCompare(b.symbol),
})
const plansAdapter = createEntityAdapter()

export const fetchStocks = createAsyncThunk('reference/stocks', async (q, { rejectWithValue }) => {
  try {
    const { data } = await api.get('/stocks/', { params: q ? { q } : {} })
    return data
  } catch (e) {
    return rejectWithValue(apiError(e))
  }
})

export const createStock = createAsyncThunk('reference/createStock', async (body, { rejectWithValue }) => {
  try {
    const { data } = await api.post('/stocks/', body)
    return data
  } catch (e) {
    return rejectWithValue(apiError(e, 'That symbol could not be added.'))
  }
})

export const fetchPlans = createAsyncThunk('reference/plans', async (_, { rejectWithValue }) => {
  try {
    const { data } = await api.get('/broker-plans/', { params: { exchange: 'NSE' } })
    return data
  } catch (e) {
    return rejectWithValue(apiError(e))
  }
})

const initialState = {
  stocks: stocksAdapter.getInitialState(),
  plans: plansAdapter.getInitialState(),
  status: 'idle',
}

const referenceSlice = createSlice({
  name: 'reference',
  initialState,
  reducers: {},
  extraReducers: (b) => {
    b.addCase(fetchStocks.fulfilled, (s, a) => {
      stocksAdapter.setAll(s.stocks, a.payload)
      s.status = 'succeeded'
    })
      .addCase(createStock.fulfilled, (s, a) => {
        stocksAdapter.upsertOne(s.stocks, a.payload)
      })
      .addCase(fetchPlans.fulfilled, (s, a) => {
        plansAdapter.setAll(s.plans, a.payload)
      })
  },
})

export const { selectAll: selectAllStocks, selectById: selectStockById } =
  stocksAdapter.getSelectors((s) => s.reference.stocks)

export const { selectAll: selectAllPlans, selectById: selectPlanById } =
  plansAdapter.getSelectors((s) => s.reference.plans)

/** Cheapest plan first, so the comparison in Settings reads top-down. */
export const selectPlansByCost = createSelector([selectAllPlans], (plans) =>
  [...plans].sort((a, b) => a.display_name.localeCompare(b.display_name)),
)

export const makeSelectStockBySymbol = (symbol) =>
  createSelector([selectAllStocks], (stocks) =>
    stocks.find((s) => s.symbol.toUpperCase() === String(symbol).toUpperCase()),
  )

export default referenceSlice.reducer
