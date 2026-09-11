# Kairos — Intent-Driven Dynamic Pricing Commerce Engine

Kairos is a full-stack e-commerce platform whose prices **move in real time with demand**.
Every product view, cart add, checkout and purchase is an *intent signal*. A pricing engine turns
the last hour of signals into a demand score and reprices products inside seller-defined bounds —
surge pricing for e-commerce — while an **event-sourced audit log** records every change and why it happened.

**Stack:** FastAPI · PostgreSQL · Redis · Kafka · Stripe · React 18 + Vite + Tailwind

---

## Features

**Pricing engine**
- Weighted intent signals in a 1-hour sliding window (Redis) → demand score → price multiplier
- Scarcity bonus when stock is low *and* demand is high
- Hard clamp to the seller's `min_price` / `max_price`
- Background repricer lets prices drift back when demand decays
- Live price pushes over WebSockets — product pages and the seller dashboard update instantly

**Event sourcing**
- Append-only `event_store` with gap-free per-aggregate versions
- Public price history on every product page (Kairos vs. seller changes)
- Full audit log per product for its seller (who changed what, and the demand data behind each automated change)

**Storefront**
- Browse, search, category filters, "Trending now" (built by the Kafka event worker)
- Cart that always shows the live price (and flags items repriced since you added them)
- Checkout with **Stripe** (test or live) — or **mock payments** when Stripe isn't configured
- Order history, pay later, cancel unpaid orders (stock is returned)

**Seller dashboard**
- List products, edit details / price bounds / images / attributes
- Change base price (reason required, audited), adjust stock, hide/show, delete
- Live demand score, viewers, cart adds and multiplier per product; full event history

**Admin**
- Manage categories, see all orders, move orders through `paid → processing → shipped → delivered`

**Hardening**
- JWT access + refresh tokens, bcrypt, role-based access (customer / seller / admin)
- Rate limits on login, registration and intent tracking; `PurchaseCompleted` can only come from the server
- Stripe webhook signature verification; idempotent payment handlers (safe under Stripe retries)
- Row-level locks at checkout — no overselling under concurrency

---

## Architecture

```mermaid
flowchart LR
    B["React SPA<br/>(Vite + Tailwind)"] -- "REST /api/v1" --> API[FastAPI]
    B -- "WebSocket /ws/*" --> API
    API --> PG[("PostgreSQL<br/>read models + event_store")]
    API --> R[("Redis<br/>intent windows · carts · pub/sub")]
    API -- "product / intent / order events" --> K{{Kafka}}
    K --> W["Event worker<br/>(trending)"] --> R
    S[Stripe] -- webhooks --> API
    RP["Repricer loop"] -.-> API
```

- **PostgreSQL** holds the read models (`products`, `orders`, …) and the immutable `event_store`.
- **Redis** holds the demand windows, carts, and the pub/sub channels that feed WebSockets.
- **Kafka** is optional. Without it, events are still stored in Postgres; only "Trending now" is empty.

### How a price is computed

| Signal | Weight |   | Demand band | Score | Multiplier |
|---|---:|---|---|---|---:|
| `ProductViewed` | 1.0 | | low | < 5 | ×0.97 |
| `ProductSearched` | 0.5 | | medium | 5 – 15 | ×1.00 |
| `WishlistAdded` | 2.0 | | high | 15 – 35 | ×1.05 |
| `CartAdded` | 5.0 | | surge | ≥ 35 | ×1.12 |
| `CartRemoved` | −4.0 | | | | |
| `CheckoutStarted` | 8.0 | | | | |
| `CheckoutAbandoned` | −3.0 | | | | |
| `PurchaseCompleted` | 10.0 | | | | |

```
new_price = base_price × demand_multiplier × stock_multiplier     (stock bonus up to ×1.08)
            → rounded to 2 decimals → clamped to [min_price, max_price]
```

Signals expire after an hour. Every `REPRICE_INTERVAL_SECONDS` (default 60) the repricer re-scores products
that have live signals or are priced away from base, so surges wind down on their own.

---

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m app.seed      # demo users, categories, products
```

| URL | What |
|---|---|
| http://localhost:5173 | Storefront |
| http://localhost:8000/docs | Interactive API docs |
| http://localhost:8000/health | Health (checks DB + Redis) |

Demo accounts (created by the seed — development only):

| Role | Email | Password |
|---|---|---|
| Seller | `naresh@kairos.dev` | `Kairos123` |
| Customer | `customer@kairos.dev` | `Customer123` |
| Admin | `admin@kairos.dev` | `Admin1234` |

**See it work:** sign in as the seller in one browser and open the Dashboard. In a private window, sign in as the
customer, open a product and add it to the cart a few times — the price and demand badge change live in both windows.

Useful `make` targets: `make seed`, `make logs`, `make worker-logs`, `make test`, `make db-shell`,
`make create-admin email=you@example.com password=Secret123`.

---

## Run without Docker

Requirements: **Python 3.12 or 3.13**, **Node 20+**, **PostgreSQL 14+**, **Redis 6+**. Kafka is optional.

```bash
# Backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # set KAFKA_ENABLED=false if you have no Kafka
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

```bash
# Frontend (second terminal)
cd frontend
cp .env.example .env
npm install
npm run dev
```

```bash
# Event worker (optional, needs Kafka) — powers "Trending now"
python -m app.consumers.worker
```

---

## Payments

**Mock mode (default).** With the placeholder Stripe values from `.env.example`, checkout creates a mock payment
and the UI shows a *Simulate successful payment* button. No keys needed.

**Stripe test mode.**
1. Put your test keys in `.env` (`STRIPE_SECRET_KEY=sk_test_…`) and `frontend/.env` (`VITE_STRIPE_PUBLISHABLE_KEY=pk_test_…`).
2. Forward webhooks and copy the signing secret it prints into `STRIPE_WEBHOOK_SECRET`:
   ```bash
   stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
   ```
3. Pay with card `4242 4242 4242 4242`, any future date, any CVC. The webhook marks the order `paid`.

In production, add a webhook endpoint in the Stripe dashboard for `payment_intent.succeeded` and
`payment_intent.payment_failed`. Unsigned webhooks are rejected whenever real Stripe keys are configured.

---

## Tests

```bash
pytest
```

- **Unit tests** (pricing math, Redis scoring, trending) always run — Redis is faked in-memory.
- **API integration tests** (auth, RBAC, product lifecycle, pricing through the API, cart, checkout, mock payments,
  cancellations, webhook idempotency, fulfilment, repricer) need PostgreSQL. They create and migrate a `kairos_test`
  database and are **skipped** if it isn't reachable. Point them elsewhere with
  `TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/kairos_test`.
- In Docker: `make test`. CI runs the full suite against a Postgres service and also builds the frontend.

---

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | — (required) | `postgresql+asyncpg://…` (`postgres://` URLs are converted automatically) |
| `SECRET_KEY` | — (required) | JWT signing key — `openssl rand -hex 32` |
| `REDIS_URL` | `redis://localhost:6379` | |
| `KAFKA_ENABLED` | `true` | `false` skips Kafka entirely |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | |
| `DEBUG` | `true` | `false` hides `/docs` and enforces `CORS_ORIGINS` |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated, used when `DEBUG=false` |
| `REPRICE_INTERVAL_SECONDS` | `60` | `0` disables the background repricer |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | `30` / `7` | |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | placeholders | Placeholders = mock payments |
| `VITE_API_URL` (frontend) | `http://localhost:8000` | |
| `VITE_STRIPE_PUBLISHABLE_KEY` (frontend) | empty | Needed only with real Stripe keys |

---

## API overview

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register` · `POST /auth/login` · `POST /auth/refresh` · `GET /auth/me` |
| Products | `GET /products` · `GET /products/{id}` · `GET /products/trending` · `GET /products/{id}/price-history` |
| Seller | `POST /products` · `GET /products/mine` · `PATCH /products/{id}` · `PUT /products/{id}/price` · `PATCH /products/{id}/stock` · `POST /products/{id}/activate` · `POST /products/{id}/deactivate` · `DELETE /products/{id}` · `GET /products/{id}/events` |
| Pricing | `POST /intent/track` · `POST /intent/track/authenticated` · `GET /intent/score/{id}` |
| Cart | `GET/POST/PATCH/DELETE /cart` |
| Orders | `POST /orders/checkout` · `GET /orders` · `GET /orders/{id}` · `GET /orders/{id}/payment` · `POST /orders/{id}/cancel` · `POST /orders/{id}/mock-payment` |
| Admin | `GET /orders/all` · `PATCH /orders/{id}/status` · `POST/PATCH/DELETE /categories` |
| Realtime | `WS /ws/prices/{product_id}` · `WS /ws/dashboard?token=…` |
| Webhooks | `POST /webhooks/stripe` |

All REST paths are prefixed with `/api/v1`. Full schemas at `/docs`.

---

## Project structure

```
app/
  api/v1/          route handlers (thin — call services)
  services/        business logic: products, cart, orders, intent, pricing engine, repricing
  consumers/       Kafka event worker + trending leaderboard
  events/          event types, Kafka publisher, event-store helper
  models/          SQLAlchemy models (read models + event_store)
  schemas/         Pydantic request/response models
  core/            config, security, logging, rate limiting
  seed.py          demo data / create-admin
alembic/           database migrations
frontend/          React SPA (pages, components, contexts, hooks)
tests/             unit + API integration tests
```

---

## Deployment

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/nare-shh/kairos)

**Render (free, one click).** `render.yaml` is a Blueprint that creates the web service (API + built frontend
on one URL), a free PostgreSQL and a free Redis-compatible Key Value, generates `SECRET_KEY`, and seeds the demo
store on start (`SEED_DEMO_DATA=true`). Click the button (or *New → Blueprint* in the Render dashboard), pick the
repo, and *Apply*. Every push to `main` redeploys. Free-tier caveats: the service sleeps after 15 minutes idle
(~1 minute to wake) and the free database expires after 30 days unless upgraded.

The Docker image builds the React app and FastAPI serves it, so in production the frontend calls the API on
its own origin — no `VITE_API_URL` or CORS setup needed.

**Other hosts (Railway, Fly…)** — the same `Dockerfile` runs migrations and starts Uvicorn on `$PORT`
(`railway.toml` is included). Provision PostgreSQL and Redis, then set:
`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `APP_ENV=production`, `DEBUG=false`,
`CORS_ORIGINS=https://<your-frontend>`, `KAFKA_ENABLED=false` (unless you run Kafka), and Stripe keys.
Create an admin with `python -m app.seed create-admin <email> <password>`.

**Frontend (Vercel, Netlify…)** — root directory `frontend`, build `npm run build`, output `dist`.
Set `VITE_API_URL` (and `VITE_STRIPE_PUBLISHABLE_KEY` for real payments). `vercel.json` handles SPA routing.

---

## Known limitations

- Single currency (INR), flat 18% GST, free shipping.
- Product images are URLs — there is no file upload/storage.
- No refunds, wishlist UI, or email notifications yet.
- Intent signals are rate-limited per IP but not de-duplicated per session; price moves are always bounded by
  the seller's min/max, but many IPs could still nudge a price within that range.
- The products table is a projection of the event store, but there is no replay/rebuild command.
