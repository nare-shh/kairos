from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import auth, cart, categories, intent, orders, products, webhooks
from app.api.v1 import websocket as ws
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.rate_limit import limiter
from app.db.redis import close_redis, init_redis
from app.db.session import Base, engine
from app.events.publisher import close_kafka_producer, init_kafka_producer

# Import all models — required so SQLAlchemy's Base registers all tables
from app.models import category as _category_models   # noqa: F401
from app.models import event_store as _event_models   # noqa: F401
from app.models import order as _order_models         # noqa: F401
from app.models import product as _product_models     # noqa: F401
from app.models import user as _user_models           # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ───────────────────────────────────────────────────────────────
    setup_logging()

    # NOTE: Migrations run via scripts/start.sh BEFORE uvicorn starts.
    # We do NOT call create_all() here — that's Alembic's job now.

    await init_redis()
    await init_kafka_producer()
    print(f"✓ Kairos [{settings.APP_ENV}] ready — http://localhost:8000/docs")

    yield  # ← app serves requests here

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    await close_kafka_producer()
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="Kairos",
    description="""
## Intent-Driven Dynamic Pricing Commerce Engine

Kairos adjusts product prices in **real-time** based on user demand signals.

### Modules
| Module | Endpoints | Description |
|--------|-----------|-------------|
| Auth | `/api/v1/auth/*` | Register, login, JWT tokens |
| Products | `/api/v1/products/*` | Catalog with full event history |
| Categories | `/api/v1/categories/*` | Product category tree |
| Intent | `/api/v1/intent/*` | Track demand signals → trigger pricing |
| Cart | `/api/v1/cart` | Redis-backed shopping cart |
| Orders | `/api/v1/orders/*` | Checkout with Stripe payments |
| Webhooks | `/api/v1/webhooks/stripe` | Stripe payment events |
| WebSocket | `/ws/prices/{id}` | Live price updates |
    """,
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Rate Limiting ──────────────────────────────────────────────────────────────
# Must be added BEFORE other middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://yourfrontend.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global error handler — never expose stack traces to clients ────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catches any unhandled exception.
    In production: log the error internally, return a safe generic message.
    Without this: FastAPI returns the full Python traceback to the client —
    which leaks internal details that attackers can exploit.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
        # Never include str(exc) here in production — it may contain sensitive info
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,        prefix="/api/v1")
app.include_router(products.router,    prefix="/api/v1")
app.include_router(categories.router,  prefix="/api/v1")
app.include_router(intent.router,      prefix="/api/v1")
app.include_router(cart.router,        prefix="/api/v1")
app.include_router(orders.router,      prefix="/api/v1")
app.include_router(webhooks.router,    prefix="/api/v1")
app.include_router(ws.router)


# ── System Endpoints ──────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint — pinged by Railway/load balancers every 30s.
    Returns 200 = instance is healthy.
    Returns 503 = instance is unhealthy → remove from rotation.
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "env": settings.APP_ENV,
    }


@app.get("/", tags=["System"])
async def root():
    return {"message": "Welcome to Kairos — Intent-Driven Dynamic Pricing Engine"}
