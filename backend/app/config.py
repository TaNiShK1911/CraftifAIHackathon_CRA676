"""
config.py — Settings loaded from environment variables / .env file.
All thresholds here can be tuned during the demo without code changes.
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MQTT
    mqtt_host: str = Field(
        default_factory=lambda: os.environ.get("SITEGUARD_MQTT_HOST", os.environ.get("MQTT_HOST", "localhost"))
    )
    mqtt_port: int = Field(
        default_factory=lambda: int(os.environ.get("SITEGUARD_MQTT_PORT", os.environ.get("MQTT_PORT", "1883")))
    )
    mqtt_topic: str = Field(
        default_factory=lambda: os.environ.get("SITEGUARD_MQTT_TOPIC", os.environ.get("MQTT_TOPIC", "pipegen/detection/demo"))
    )

    # PipeGen output
    pipegen_output_dir: str = "/tmp/pipegen_out"
    media_video_path: str = "/tmp/pipegen_out/annotated.mp4"

    # Database
    db_path: str = Field(
        default_factory=lambda: os.environ.get(
            "SITEGUARD_DB_PATH",
            os.environ.get("DB_PATH", str(Path(__file__).resolve().parent.parent.parent / "data" / "siteguard.db"))
        )
    )

    # CORS
    cors_origins: str = "http://localhost:5173"

    # Rules engine thresholds
    min_consecutive_frames: int = 5
    quiet_seconds: int = 8
    loiter_seconds: int = 10

    # Throttle: one stored raw event per (key, N ms)
    event_throttle_ms: int = 500

    # SSE heartbeat interval in seconds
    sse_heartbeat_seconds: int = 15

    @field_validator("db_path")
    @classmethod
    def ensure_db_dir(cls, v: str) -> str:
        Path(v).parent.mkdir(parents=True, exist_ok=True)
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def adapter_yaml_path(self) -> Path:
        return Path(__file__).parent.parent / "config" / "adapter.yaml"

    @property
    def zones_yaml_path(self) -> Path:
        return Path(__file__).parent.parent / "config" / "zones.yaml"


settings = Settings()
