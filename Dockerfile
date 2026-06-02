# ─── Stage 1: Base image ──────────────────────────────────────────────────────
# python:3.12-slim = Python 3.12 on minimal Linux (no bloat, smaller image)
# "slim" vs full: full is ~900MB, slim is ~130MB — always use slim in production
FROM python:3.12-slim

# Set working directory inside the container
# All subsequent commands run from this path
WORKDIR /app

# Environment variables that control Python's behavior inside Docker
ENV PYTHONDONTWRITEBYTECODE=1 \
    # Don't write .pyc files (compiled bytecode) — not needed in containers
    PYTHONUNBUFFERED=1
    # Don't buffer stdout/stderr — logs appear immediately instead of in batches

# Copy requirements first — before copying your code
# Why? Docker caches each layer. If requirements haven't changed,
# Docker reuses the cached layer and skips re-installing packages.
# This makes rebuilds much faster during development.
COPY requirements.txt .

# Install dependencies
# --retries 5  : retry each failed download up to 5 times (fixes network drops)
# --timeout 120: wait 120s per connection before giving up (slow networks)
# --default-timeout: same as above, belt-and-suspenders for older pip versions
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt

# Now copy the rest of the application code
# This layer changes often (every code edit), so it comes LAST
COPY . .

# Document which port the app listens on (doesn't actually open the port)
EXPOSE 8000

# The command that runs when the container starts
# uvicorn = ASGI server | app.main:app = file path : FastAPI instance
# --host 0.0.0.0 = listen on all interfaces (required inside Docker)
# --port 8000 = port number
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
