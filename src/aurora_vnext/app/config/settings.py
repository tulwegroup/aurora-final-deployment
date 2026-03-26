"""
Aurora OSI vNext — Application Settings
Loads and validates all environment variables.
No scientific logic. No scoring. No thresholds.
"""

from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogFormat(str, Enum):
    JSON = "json"
    TEXT = "text"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Core application
    # -------------------------------------------------------------------------
    aurora_env: Environment = Environment.DEVELOPMENT
    aurora_secret_key: str = Field(min_length=32)
    aurora_admin_user: str = "admin"
    aurora_admin_pass: str = Field(min_length=12)

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    aurora_db_host: str = "localhost"
    aurora_db_port: int = 5432
    aurora_db_name: str = "aurora_vnext"
    aurora_db_user: str = "aurora"
    aurora_db_pass: str = "aurora_dev_password"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.aurora_db_user}:{self.aurora_db_pass}"
            f"@{self.aurora_db_host}:{self.aurora_db_port}/{self.aurora_db_name}"
        )

    # -------------------------------------------------------------------------
    # Storage
    # -------------------------------------------------------------------------
    aurora_s3_bucket_scans: str = "aurora-scan-artifacts"
    aurora_s3_bucket_twin: str = "aurora-twin-store"
    aurora_s3_bucket_exports: str = "aurora-exports"
    aurora_s3_region: str = "us-east-1"

    # -------------------------------------------------------------------------
    # Task queue
    # -------------------------------------------------------------------------
    aurora_sqs_scan_queue_url: str = ""
    aurora_sqs_dlq_url: str = ""

    # -------------------------------------------------------------------------
    # Cache
    # -------------------------------------------------------------------------
    aurora_redis_url: str = "redis://localhost:6379/0"

    # -------------------------------------------------------------------------
    # External services
    # -------------------------------------------------------------------------
    gee_project_id: str = ""
    gee_service_account_key: str = ""

    # -------------------------------------------------------------------------
    # JWT
    # -------------------------------------------------------------------------
    aurora_jwt_private_key_path: str = "./keys/jwt_private.pem"
    aurora_jwt_public_key_path: str = "./keys/jwt_public.pem"
    aurora_jwt_access_expiry_min: int = 15
    aurora_jwt_refresh_expiry_days: int = 7

    # -------------------------------------------------------------------------
    # Version registry (pinned — must match commodity library)
    # -------------------------------------------------------------------------
    aurora_score_version: str = "0.1.0"
    aurora_tier_version: str = "0.1.0"
    aurora_causal_graph_version: str = "0.1.0"
    aurora_physics_model_version: str = "0.1.0"
    aurora_temporal_model_version: str = "0.1.0"
    aurora_province_prior_version: str = "0.1.0"
    aurora_commodity_library_version: str = "0.1.0"
    aurora_scan_pipeline_version: str = "0.1.0"

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------
    aurora_log_level: str = "INFO"
    aurora_log_format: LogFormat = LogFormat.TEXT

    @property
    def is_production(self) -> bool:
        return self.aurora_env == Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """Cached singleton settings instance."""
    return Settings()