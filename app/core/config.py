from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"

    # Auth — these have no defaults so the app crashes fast if missing
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Tell pydantic-settings to read from .env file
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Single instance used everywhere — import this, not the class
# This pattern is called a "singleton" — one shared config object
settings = Settings()
