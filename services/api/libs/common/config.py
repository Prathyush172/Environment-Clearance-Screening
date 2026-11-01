"""Central configuration management using Pydantic Settings v2."""

from typing import Optional
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === LLM PROVIDER CONFIG ===
    LLM_PROVIDER: str = "stub"
    LLM_MODEL_ID: str = "gemini-3-flash-preview"
    LLM_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None

    # === FALLBACK LLM ===
    FALLBACK_LLM_PROVIDER: str = "stub"
    FALLBACK_LLM_MODEL_ID: Optional[str] = None
    FALLBACK_LLM_API_KEY: Optional[str] = None
    FALLBACK_LLM_BASE_URL: Optional[str] = None

    # === VERIFIER LLM ===
    VERIFIER_LLM_PROVIDER: Optional[str] = None
    VERIFIER_LLM_MODEL_ID: Optional[str] = None
    VERIFIER_LLM_API_KEY: Optional[str] = None
    VERIFIER_LLM_BASE_URL: Optional[str] = None

    # === DATABASE ===
    DATABASE_URL: str = "postgresql+asyncpg://eia_user:eia_password@postgres:5432/eia_db"
    POSTGRES_USER: str = "eia_user"
    POSTGRES_PASSWORD: str = "eia_password"
    POSTGRES_DB: str = "eia_db"

    # === REDIS ===
    REDIS_URL: str = "redis://redis:6379/0"

    # === CHROMA ===
    CHROMA_HOST: str = "chroma"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "eia_corpus"
    CHROMA_PERSIST_DIRECTORY: str = "./data/chroma"
    CHROMA_URL: Optional[str] = None

    # === ADMIN ===
    ADMIN_TOKEN: str = "change-me-admin-token-32chars-min"
    ADMIN_FAULTS_ENABLED: bool = False

    # === AUTH ===
    JWT_SECRET_KEY: str = "change-me-jwt-secret-key-32chars-min-dev-only"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    AUTH_MAX_FAILED_ATTEMPTS: int = 5
    AUTH_LOCKOUT_MINUTES: int = 5

    # === LLM STUB ===
    STUB_DELAY_MS_MIN: int = 1500
    STUB_DELAY_MS_MAX: int = 4000
    STUB_ERROR_RATE: float = 0.0

    # === AGENT LOOP BOUNDS ===
    MAX_STEPS: int = 12
    MAX_TOOL_CALLS: int = 15
    RUN_WALL_CLOCK_SECONDS: int = 90
    MAX_VERIFY_ATTEMPTS: int = 2
    MAX_REPLANS: int = 2

    # === GUARDRAILS ===
    GUARDRAIL_CLASSIFIER_ENABLED: bool = True
    TOXICITY_THRESHOLD: float = 0.8
    INJECTION_BLOCK_SEVERITY: str = "high"

    # === RATE LIMITING ===
    RATE_LIMIT_RPM_PER_CLIENT: int = 60
    RATE_LIMIT_RPM_PER_IP: int = 120
    MAX_CONCURRENT_RUNS_PER_CLIENT: int = 5
    DAILY_TOKEN_BUDGET_PER_CLIENT: int = 1000000

    # === CIRCUIT BREAKER ===
    BREAKER_FAILURE_THRESHOLD: int = 5
    BREAKER_RECOVERY_TIMEOUT_S: int = 30
    BREAKER_HALF_OPEN_MAX_CALLS: int = 2

    # === GATEWAY ===
    GATEWAY_TIMEOUT_S: int = 30
    GATEWAY_MAX_RETRIES: int = 3
    GATEWAY_RETRY_MAX_WAIT_S: int = 60

    # === VERIFIER SERVICE ===
    VERIFIER_HOST: str = "verifier"
    VERIFIER_PORT: int = 8001
    VERIFIER_TIMEOUT_S: int = 30
    VERIFIER_URL: Optional[str] = None

    # === FEATURE FLAGS ===
    FEATURE_MODIFIER_CHECK_ENABLED: bool = True

    # === QUALITY / EVAL ===
    QUALITY_SAMPLE_RATE: float = 0.1

    # === CALLBACKS ===
    CALLBACK_HMAC_SECRET: str = "change-me-hmac-secret-32chars"

    # === EMBEDDING & CACHE ===
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_CACHE_ENABLED: bool = True
    RETRIEVAL_CACHE_ENABLED: bool = True
    RUN_CACHE_ENABLED: bool = True

    # === OBSERVABILITY ===
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector:4317"
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    # === INGEST ===
    CORPUS_DIR: str = "/data/corpus"


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()


settings = get_settings()
