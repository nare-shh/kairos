"""
Production Logging Configuration
══════════════════════════════════

In development:   print() and plain text logs are fine
In production:    logs must be structured JSON so tools can parse them

Why JSON logs?
──────────────
Plain text:  "ERROR 2025-01-01 User not found id=abc"
             → hard to search, filter, or alert on

JSON:         {"level": "ERROR", "time": "...", "msg": "User not found", "user_id": "abc"}
             → Railway, Datadog, CloudWatch can filter: level=ERROR, alert on error rate

Every log line is a searchable record.
"""

import logging
import sys
from app.core.config import settings


def setup_logging() -> None:
    """
    Configure logging for the entire application.
    Called once at startup in main.py lifespan.

    Dev mode:  human-readable colored output
    Prod mode: JSON structured output (machine-readable)
    """

    if settings.APP_ENV == "production":
        # JSON formatter — every log line is a valid JSON object
        try:
            from pythonjsonlogger import jsonlogger

            formatter = jsonlogger.JsonFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        except ImportError:
            # Fallback if pythonjsonlogger not installed
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
    else:
        # Dev: readable format with colors via uvicorn's default handler
        formatter = logging.Formatter(
            fmt="%(levelname)s:     %(name)s - %(message)s"
        )

    # Root logger — all loggers in the app inherit from this
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO if settings.APP_ENV == "production" else logging.DEBUG)

    # Console handler — writes to stdout (Docker/Railway captures this)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Remove any existing handlers (avoid duplicate log lines)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING if settings.APP_ENV == "production" else logging.INFO
    )
    logging.getLogger("aiokafka").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.info(f"Logging configured: env={settings.APP_ENV}")
