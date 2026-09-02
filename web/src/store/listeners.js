import { createListenerMiddleware, isRejectedWithValue } from '@reduxjs/toolkit'

import { tokens } from '../api/client'
import { sessionExpired } from './authSlice'

/**
 * One place that reacts to cross-cutting events, instead of every component
 * checking for an expired session.
 */
export const listenerMiddleware = createListenerMiddleware()

listenerMiddleware.startListening({
  predicate: (action) =>
    isRejectedWithValue(action) &&
    typeof action.payload === 'string' &&
    /credentials were not provided|token .*(invalid|expired)/i.test(action.payload),
  effect: async (_action, api) => {
    tokens.clear()
    api.dispatch(sessionExpired())
  },
})
