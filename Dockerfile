FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt

COPY . .

# Fix line endings + make executable (handles Windows CRLF → Unix LF)
RUN sed -i 's/\r//' scripts/start.sh && chmod +x scripts/start.sh

EXPOSE 8000

CMD ["scripts/start.sh"]
