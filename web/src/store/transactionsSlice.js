import { createAsyncThunk, createEntityAdapter, createSlice } from '@reduxjs/toolkit'

import api, { apiError } from '../api/client'
import { fetchPortfolio, fetchSummary } from './portfolioSlice'

const txnAdapter = createEntityAdapter({
  sortComparer: (a, b) =>
    b.trade_date.localeCompare(a.trade_date) || b.sequence_no - a.sequence_no,
})

export const fetchTransactions = createAsyncThunk(
  'transactions/fetch',
  async (params = {}, { rejectWithValue }) => {
    try {
      const { data } = await api.get('/transactions/', { params })
      return data.results ?? data
    } catch (e) {
      return rejectWithValue(apiError(e))
    }
  },
)

/** Live charge preview — computed server-side, nothing saved. */
export const previewTransaction = createAsyncThunk(
  'transactions/preview',
  async (body, { rejectWithValue }) => {
    try {
      const { data } = await api.post('/transactions/preview/', body)
      return data
    } catch (e) {
      return rejectWithValue(apiError(e))
    }
  },
)

export const createTransaction = createAsyncThunk(
  'transactions/create',
  async (body, { dispatch, rejectWithValue }) => {
    try {
      const { data } = await api.post('/transactions/', body)
      dispatch(fetchPortfolio())
      dispatch(fetchSummary())
      return data
    } catch (e) {
      return rejectWithValue(apiError(e, 'The transaction could not be recorded.'))
    }
  },
)

export const deleteTransaction = createAsyncThunk(
  'transactions/delete',
  async (id, { dispatch, rejectWithValue }) => {
    try {
      await api.delete(`/transactions/${id}/`)
      dispatch(fetchPortfolio())
      dispatch(fetchSummary())
      return id
    } catch (e) {
      return rejectWithValue(apiError(e))
    }
  },
)

const initialState = txnAdapter.getInitialState({
  status: 'idle',
  preview: null,
  previewStatus: 'idle',
  submitStatus: 'idle',
  error: null,
})

const transactionsSlice = createSlice({
  name: 'transactions',
  initialState,
  reducers: {
    clearPreview(state) {
      state.preview = null
      state.previewStatus = 'idle'
    },
    clearSubmit(state) {
      state.submitStatus = 'idle'
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchTransactions.pending, (s) => {
        s.status = 'loading'
      })
      .addCase(fetchTransactions.fulfilled, (s, a) => {
        txnAdapter.setAll(s, a.payload)
        s.status = 'succeeded'
      })
      .addCase(fetchTransactions.rejected, (s, a) => {
        s.status = 'failed'
        s.error = a.payload
      })

      .addCase(previewTransaction.pending, (s) => {
        s.previewStatus = 'loading'
      })
      .addCase(previewTransaction.fulfilled, (s, a) => {
        s.preview = a.payload
        s.previewStatus = 'succeeded'
      })
      .addCase(previewTransaction.rejected, (s) => {
        s.previewStatus = 'failed'
        s.preview = null
      })

      .addCase(createTransaction.pending, (s) => {
        s.submitStatus = 'saving'
        s.error = null
      })
      .addCase(createTransaction.fulfilled, (s, a) => {
        txnAdapter.upsertOne(s, a.payload)
        s.submitStatus = 'saved'
        s.preview = null
      })
      .addCase(createTransaction.rejected, (s, a) => {
        s.submitStatus = 'failed'
        s.error = a.payload
      })
      .addCase(deleteTransaction.fulfilled, (s, a) => {
        txnAdapter.removeOne(s, a.payload)
      })
  },
})

export const { clearPreview, clearSubmit } = transactionsSlice.actions

export const {
  selectAll: selectAllTransactions,
  selectById: selectTransactionById,
} = txnAdapter.getSelectors((s) => s.transactions)

export const selectPreview = (s) => s.transactions.preview
export const selectPreviewStatus = (s) => s.transactions.previewStatus
export const selectSubmitStatus = (s) => s.transactions.submitStatus
export const selectTransactionError = (s) => s.transactions.error

export default transactionsSlice.reducer
