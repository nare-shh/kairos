"""
Rate Limiting
═════════════
Prevents API abuse: bots, scrapers, brute-force attacks.

How it works:
─────────────
Each client (identified by IP) gets a quota per time window.
Example: 100 requests per minute.
When they exceed it → 429 Too Many Requests.

We use slowapi — a FastAPI wrapper around the limits library.
Storage backend: Redis — shared across all API instances (important for horizontal scaling).
If you have 3 API servers and store limits in-memory, each server thinks the
client only used 1/3 of their quota. Redis is the single shared counter.

Usage in routes:
────────────────
    @router.get("/products")
    @limiter.limit("60/minute")    # ← this route: 60 req/min per IP
    async def list_products(request: Request, ...):
        ...

    @router.post("/auth/login")
    @limiter.limit("10/minute")    # ← login: stricter (brute-force protection)
    async def login(request: Request, ...):
        ...
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# get_remote_address: extracts the client's IP from the request
# This is the "key" — each unique IP gets its own quota
# In production behind a load balancer, also check X-Forwarded-For header
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],   # global default for all routes
    # Override per-route with @limiter.limit("N/period")
)
