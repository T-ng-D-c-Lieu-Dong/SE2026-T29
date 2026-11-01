from functools import lru_cache
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BOOKING_",
        env_ignore_empty=True,
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://booking:booking@localhost:5432/booking"
    release: str = "dev"
    export_api_keys: str = ""
    commit_sha: str = "unknown"
    db_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    fault_mode: Literal["off", "error", "latency"] = "off"
    fault_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    fault_until: AwareDatetime | None = None
    fault_latency_seconds: float = Field(default=3.0, ge=0.0, le=30.0)
    telemetry_enabled: bool = False
    service_name: str = "booking-api"
    deployment_environment: str = "local"
    otlp_endpoint: str = "http://otel-collector:4317"
    otlp_insecure: bool = True
    telemetry_exporter_timeout_millis: int = Field(default=2_000, gt=0, le=30_000)
    telemetry_max_queue_size: int = Field(default=512, gt=0, le=16_384)
    telemetry_max_export_batch_size: int = Field(default=64, gt=0, le=4_096)
    telemetry_schedule_delay_millis: int = Field(default=1_000, gt=0, le=60_000)
    telemetry_metric_export_interval_millis: int = Field(
        default=10_000,
        gt=0,
        le=300_000,
    )
    telemetry_export_logs: bool = True

    @model_validator(mode="after")
    def validate_safety_controls(self) -> "Settings":
        if self.fault_mode != "off" and self.fault_until is None:
            raise ValueError("BOOKING_FAULT_UNTIL is required while fault injection is active")
        if self.telemetry_max_export_batch_size > self.telemetry_max_queue_size:
            raise ValueError(
                "BOOKING_TELEMETRY_MAX_EXPORT_BATCH_SIZE cannot exceed "
                "BOOKING_TELEMETRY_MAX_QUEUE_SIZE"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
