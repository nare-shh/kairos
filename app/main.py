from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth
from app.core.config import settings
from app.db.redis import close_redis, init_redis
from app.db.session import Base, engine
from app.models import user as _user_models  # noqa: F401 — imported so Base sees the table


# lifespan is a modern FastAPI pattern for startup/shutdown logic
# Code before "yield" runs when the app starts
# Code after "yield" runs when the app shuts down
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    # Create all database tables that don't exist yet
    # In production you'd use Alembic migrations instead, but this is fine for dev
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Connect to Redis
    await init_redis()

    print(f"Kairos starting in {settings.APP_ENV} mode")

    yield  # App is now running and serving requests

    # SHUTDOWN
    await close_redis()
    await engine.dispose()  # Close all database connections cleanly


# Create the FastAPI application instance
app = FastAPI(
    title="Kairos",
    description="Intent-Driven Dynamic Pricing Commerce Engine",
    version="1.0.0",
    # Swagger UI available at /docs, ReDoc at /redoc
    docs_url="/docs" if settings.DEBUG else None,   # hide docs in production
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS — controls which frontend URLs are allowed to call this API
# In production, replace "*" with your actual frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://yourfrontend.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routers ──────────────────────────────────────────────────────────────────
# include_router wires an APIRouter into the main app
# prefix="/api/v1" is prepended to all routes inside the router
# So auth's "/register" becomes "/api/v1/auth/register"
app.include_router(auth.router, prefix="/api/v1")


# Health check — the first endpoint every production API must have
# Monitoring tools ping this to know if the service is alive
@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
    }


@app.get("/", tags=["System"])
async def root():
    return {"message": "Welcome to Kairos — Intent-Driven Dynamic Pricing Engine"}
