FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .

# Install dependencies
# --retries 5  : retry each failed download up to 5 times (fixes network drops)
# --timeout 120: wait 120s per connection before giving up (slow networks)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt

COPY . .

# Make the startup script executable
# Without this, Linux will refuse to run it (permission denied)
RUN chmod +x scripts/start.sh

EXPOSE 8000

# Production: run migrations then start API
CMD ["scripts/start.sh"]
