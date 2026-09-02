# Web client

React 18 + Redux Toolkit + Vite. JavaScript, no TypeScript.

## State

```
store/
  index.js            configureStore + listener middleware
  authSlice.js        login / register / refresh-aware session
  portfolioSlice.js   holdings (entity adapter) + summary + detail
  transactionsSlice.js ledger + the live charge preview
  referenceSlice.js   stocks and broker plans (two adapters)
  listeners.js        reacts to an expired session in one place
```

Patterns used deliberately:

- **`createEntityAdapter`** for holdings, transactions, stocks and plans, so
  rows are normalised by id and a single updated holding does not re-render the
  whole table.
- **`createAsyncThunk`** for every call, with `rejectWithValue` carrying a
  readable message from the DRF error body rather than a stack trace.
- **`createSelector`** for anything derived — `selectVisibleHoldings`,
  `selectFilterCounts`, `selectStalePriceCount` — so filtering recomputes only
  when the inputs actually change.
- **`createListenerMiddleware`** so an expired session is handled once, centrally,
  instead of in every component.
- **`addMatcher`** in `authSlice` to share pending/fulfilled handling across
  login and register without duplicating reducers.

## Money

Every monetary value arrives from the API as a string and stays one. The UI
formats with `Intl.NumberFormat('en-IN')` for Indian digit grouping and never
does arithmetic on a price — the backend owns all of it.

## Scripts

```bash
npm run dev       # dev server on :5173, proxies /api to :8000
npm run build     # production bundle
npm run preview   # serve the build
```
