"""
Central configuration for AgriN Twin backend.
All secrets/keys are read from environment variables so the same codebase
runs identically in dev, judging-demo, and production deployments.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "AgriN Twin"
    ENV: str = "development"  # development | staging | production
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite:///./agrintwin.db"

    # Security
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Satellite data (Copernicus / Sentinel Hub / Google Earth Engine)
    SENTINEL_HUB_CLIENT_ID: str | None = None
    SENTINEL_HUB_CLIENT_SECRET: str | None = None
    SATELLITE_DEMO_MODE: bool = True  # falls back to physically-plausible synthetic NDVI when no creds set

    # CV disease model
    DISEASE_MODEL_PATH: str = "app/ml/weights/disease_model.keras"
    DISEASE_MODEL_DEMO_MODE: bool = False  # a real trained model ships in app/ml/weights/ — set True to force the heuristic fallback

    # Voice / LLM agent
    ANTHROPIC_API_KEY: str | None = None
    LLM_MODEL: str = "claude-sonnet-4-6"
    # Free alternative — Google AI Studio's Gemini API has a genuinely
    # free, permanent, no-credit-card tier (unlike Anthropic's one-time
    # trial credit). Used automatically if ANTHROPIC_API_KEY is empty and
    # this is set. Get a key at https://aistudio.google.com/apikey
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    SPEECH_TO_TEXT_PROVIDER: str = "whisper"  # whisper | bhashini | google
    BHASHINI_API_KEY: str | None = None  # India's national language AI mission — recommended for production

    # Federated model-exchange
    FEDERATION_NODE_ID: str = "IN-NODE-1"
    FEDERATION_REGISTRY_URL: str = "http://localhost:8000/api/v1/federation"

    # IoT ingestion
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    IOT_INGEST_API_KEY: str = "dev-pod-key-change-in-prod"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
