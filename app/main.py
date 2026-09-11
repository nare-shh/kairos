import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.v1 import auth, cart, categories, intent, orders, products, webhooks
from app.api.v1 import websocket as ws
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.rate_limit import limiter
from app.db.redis import close_redis, get_redis_or_none, init_redis
from app.db.session import engine
from app.events.publisher import close_kafka_producer, init_kafka_producer
from app.services.repricer import repricer_loop

# Import all models — required so SQLAlchemy's Base registers all tables
from app.models import category as _category_models   # noqa: F401
from app.models import event_store as _event_models   # noqa: F401
from app.models import order as _order_models         # noqa: F401
from app.models import product as _product_models     # noqa: F401
from app.models import user as _user_models           # noqa: F401

logger = logging.getLogger(__name__)

APP_VERSION = "1.1.0"

# Built React app — the Docker image builds it here. Absent in local dev (Vite serves it).
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ───────────────────────────────────────────────────────────────
    setup_logging()
    # Alembic already ran migrations (and proved DB is reachable) before uvicorn started
    # No DB retry loop needed here — if alembic succeeded, DB is accessible
    await init_redis()
    await init_kafka_producer()

    # Background repricer: lets prices decay once demand signals expire
    repricer_task = None
    if settings.REPRICE_INTERVAL_SECONDS > 0:
        repricer_task = asyncio.create_task(repricer_loop(settings.REPRICE_INTERVAL_SECONDS))

    logger.info(f"Kairos [{settings.APP_ENV}] ready")

    yield  # ← app serves requests here

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    if repricer_task:
        repricer_task.cancel()
        with suppress(asyncio.CancelledError):
            await repricer_task
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
| Products | `/api/v1/products/*` | Catalog, seller management, full event history, price history |
| Categories | `/api/v1/categories/*` | Product category tree |
| Intent | `/api/v1/intent/*` | Track demand signals → trigger pricing |
| Cart | `/api/v1/cart` | Redis-backed shopping cart with live prices |
| Orders | `/api/v1/orders/*` | Checkout, Stripe (or mock) payments, cancel, fulfilment |
| Webhooks | `/api/v1/webhooks/stripe` | Stripe payment events |
| WebSocket | `/ws/prices/{id}`, `/ws/dashboard` | Live price updates |
    """,
    version=APP_VERSION,
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
# Production origins come from CORS_ORIGINS (comma-separated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else settings.cors_origins,
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
    Returns 200 = instance is healthy (database + Redis reachable).
    Returns 503 = instance is unhealthy → remove from rotation.
    """
    checks = {"database": "ok", "redis": "ok"}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "unavailable"

    try:
        redis = get_redis_or_none()
        if redis is None:
            raise RuntimeError("Redis not initialized")
        await redis.ping()
    except Exception:
        checks["redis"] = "unavailable"

    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "app": settings.APP_NAME,
            "version": APP_VERSION,
            "env": settings.APP_ENV,
            "checks": checks,
        },
    )


# ── Frontend (production) ─────────────────────────────────────────────────────
# One service serves the SPA and the API from the same origin — no CORS, and the
# frontend needs no API URL. Must stay LAST: the catch-all only sees unmatched paths.
API_PREFIXES = ("api/", "ws/", "docs", "redoc", "openapi.json", "health")

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        # Unknown API paths stay real 404s instead of returning the HTML app
        if full_path.startswith(API_PREFIXES):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        # Real files (favicon, ...) — resolved strictly inside dist, never outside it
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST.resolve()):
            return FileResponse(candidate)
        # Everything else is a client-side route (/products/..., /orders, ...)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", tags=["System"])
    async def root():
        return {"message": "Welcome to Kairos — Intent-Driven Dynamic Pricing Engine"}
