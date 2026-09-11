from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_real_secret(value: str, prefixes: tuple[str, ...]) -> bool:
    """
    True only for values that look like real credentials.
    The placeholders in .env.example / CI ("sk_test_your_key_here", "whsec_placeholder")
    must NOT count — otherwise a fresh checkout would call Stripe with a fake key.
    """
    return value.startswith(prefixes) and not any(
        marker in value for marker in ("placeholder", "your_")
    )


class Settings(BaseSettings):
    # pydantic-settings automatically reads these from the .env file
    # The field name must match the variable name in .env (case-insensitive)

    # App
    APP_NAME: str = "Kairos"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Kafka — set KAFKA_ENABLED=false when no broker is available (e.g. Railway)
    # The app works without Kafka: events are still persisted to event_store
    KAFKA_ENABLED: bool = True
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"

    # Auth — these have no defaults so the app crashes fast if missing
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS — comma-separated frontend origins allowed when DEBUG=false
    CORS_ORIGINS: str = "http://localhost:5173"

    # Background repricer — re-scores products whose demand window decayed
    # Set to 0 to disable (tests do this)
    REPRICE_INTERVAL_SECONDS: int = 60

    # Stripe — leave empty (or as the .env.example placeholders) to use mock payments
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Tell pydantic-settings to read from .env file
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("DATABASE_URL")
    @classmethod
    def use_asyncpg_driver(cls, v: str) -> str:
        """Railway/Heroku hand out postgres:// URLs — the app needs the asyncpg driver."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def stripe_enabled(self) -> bool:
        """Real Stripe payments; otherwise checkout runs in mock-payment mode."""
        return _is_real_secret(self.STRIPE_SECRET_KEY, ("sk_test_", "sk_live_"))

    @property
    def stripe_webhook_enabled(self) -> bool:
        """Webhook signatures can only be verified when a real signing secret is set."""
        return _is_real_secret(self.STRIPE_WEBHOOK_SECRET, ("whsec_",))


# Single instance used everywhere — import this, not the class
# This pattern is called a "singleton" — one shared config object
settings = Settings()
