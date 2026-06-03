from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, products
from app.core.config import settings
from app.db.redis import close_redis, init_redis
from app.db.session import Base, engine
from app.events.publisher import close_kafka_producer, init_kafka_producer

# Import all models so SQLAlchemy's Base knows about them before create_all
# Without these imports, the tables won't be created
from app.models import category as _category_models   # noqa: F401
from app.models import event_store as _event_models   # noqa: F401
from app.models import product as _product_models     # noqa: F401
from app.models import user as _user_models           # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ───────────────────────────────────────────────────────────────
    # Create all DB tables (users, products, categories, event_store)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await init_redis()
    await init_kafka_producer()    # Connect to Kafka (gracefully skips if unavailable)

    print(f"✓ Kairos [{settings.APP_ENV}] ready — http://localhost:8000/docs")

    yield  # ← app runs here

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    await close_kafka_producer()
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="Kairos",
    description="Intent-Driven Dynamic Pricing Commerce Engine",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://yourfrontend.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")


# ─── System Endpoints ─────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME, "env": settings.APP_ENV}


@app.get("/", tags=["System"])
async def root():
    return {"message": "Welcome to Kairos — Intent-Driven Dynamic Pricing Engine"}
