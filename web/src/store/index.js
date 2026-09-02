import { configureStore } from '@reduxjs/toolkit'

import analyticsReducer from './analyticsSlice'
import authReducer from './authSlice'
import { listenerMiddleware } from './listeners'
import portfolioReducer from './portfolioSlice'
import referenceReducer from './referenceSlice'
import transactionsReducer from './transactionsSlice'

export const store = configureStore({
  reducer: {
    auth: authReducer,
    analytics: analyticsReducer,
    portfolio: portfolioReducer,
    transactions: transactionsReducer,
    reference: referenceReducer,
  },
  middleware: (getDefault) => getDefault().prepend(listenerMiddleware.middleware),
})
