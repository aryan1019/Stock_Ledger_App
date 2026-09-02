# Ledger — Stock P&L & Break-Even

Tracks Indian equity delivery positions: true cost per share, real break-even
after exit charges, and realized profit kept strictly separate from the cost of
shares you still hold.

```
Stock_App/
├── backend/            Django 5 + DRF + JWT
│   ├── calculations/   ← the engine. Pure Python, zero Django imports.
│   ├── accounts/       custom user, ownership queryset
│   ├── stocks/         stock master, corporate actions, manual prices
│   ├── charges/        broker plans as versioned data
│   ├── transactions/   the append-only ledger
│   ├── portfolio/      projections + replay orchestration
│   └── api/            serializers, views, routes
├── web/                React 18 + Redux Toolkit + Vite
└── docker-compose.yml  Postgres, optional
```

## Run it

**Backend** (terminal 1)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_plans          # loads the six broker charge plans
python manage.py runserver           # http://127.0.0.1:8000
```

**Frontend** (terminal 2)

```bash
cd web
npm install
npm run dev                          # http://localhost:5173
```

Register from the sign-in screen and record your first trade. Vite proxies
`/api` to Django, so no CORS setup is needed in development.

To use PostgreSQL instead of SQLite: `docker compose up -d db`, then set
`DATABASE_URL=postgres://ledger:ledger@localhost:5432/ledger` in `backend/.env`.

## Tests

```bash
cd backend && python -m pytest        # 90 tests
```

That covers the calculation engine (accounting rules, all six charge plans,
corporate actions, replay invariants) and the API — including a cross-user
suite that hits every endpoint as the wrong user and expects 404.

## Charges are verified, not assumed

`KOTAK_NEO:TRADE_FREE_YOUTH` is reproduced to the paisa from two real broker
bills (`backend/tests/test_kotak_bills.py`). Those bills settled four things
that published rate cards had wrong:

* the NSE transaction charge is **0.00297%**, not 0.00307% — the higher figure
  bundles IPFT, so charging both double-counted it
* there is therefore **no separate IPFT component**
* **stamp duty rounds to the nearest rupee** (7.0875 was billed as 7.00)
* the **youth plan levies no DP charge at all** on a sell

Every plan carries a `verified` flag. The five that are still `false` come from
published rate cards — compare a contract note and correct the row; the rates
are data, so it is never a code change.

## The two rules everything rests on

**The ledger is the only truth.** Position, lots and allocations are a
projection, rebuilt from scratch after every write. That is why a backdated
trade or a corrected typo can never corrupt your data — and why
`POST /api/v1/portfolio/rebuild/` is safe to call at any time.

**A sell never moves your average.** Realized profit is tracked separately and
is never used to make the cost of remaining shares look lower. The broker's
version of the number is shown beside yours on the Stock Detail screen, purely
so you can reconcile the two.

## API

Base `/api/v1/`. Money is serialised as **strings** — a portfolio total is the
last place you want binary floating point.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register/` `/auth/login/` `/auth/refresh/` `/auth/logout/` | Auth |
| GET PATCH | `/me/` | Profile and chosen broker plan |
| GET POST | `/stocks/` | Search / add a symbol |
| GET POST | `/transactions/` | Ledger |
| POST | `/transactions/preview/` | Charges + resulting position, nothing saved |
| POST | `/transactions/{id}/correct/` | Append a correction, supersede the original |
| DELETE | `/transactions/{id}/` | Supersede and replay |
| GET | `/portfolio/` `/portfolio/summary/` `/portfolio/{stock}/` | Holdings, totals, detail |
| GET | `/portfolio/analytics/` | Period P&L — `?preset=7D\|30D\|90D\|1Y\|ALL` or `?from=&to=` |
| POST | `/portfolio/rebuild/` | Rebuild every projection from the ledger |
| GET PUT | `/prices/{stock}/` | Manual market price |
| GET | `/broker-plans/` | The six seeded plans |
| GET | `/transactions/?from=&to=&type=&q=` | Filtered ledger history |
| GET POST | `/corporate-actions/` | Splits and bonuses |
