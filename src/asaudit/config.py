import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from asaudit.data.lobster import TimestampPolicy
from asaudit.data.quality import QualityPolicy


class ValidationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    depth: int = Field(default=10, ge=1)
    price_unit: Literal["0.0001"] = "0.0001"
    timezone: Literal["America/New_York"] = "America/New_York"
    reconstruction: Literal["snapshot_assisted"] = "snapshot_assisted"
    timestamp_policy: TimestampPolicy = "strict"
    quality: QualityPolicy = Field(default_factory=QualityPolicy)


class CollectorConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol: str = Field(default="BTC-USD", pattern=r"^[A-Z0-9]+-[A-Z0-9]+$")
    duration_seconds: int = Field(default=3600, gt=0)
    max_reconnects: int = Field(default=10, ge=0)
    reconnect_seconds: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    queue_capacity: int = Field(default=10000, gt=0)
    batch_size: int = Field(default=1000, gt=0)
    flush_seconds: float = Field(default=1.0, gt=0, allow_inf_nan=False)


def validation_config(path: Path | None) -> ValidationConfig:
    if path is None:
        return ValidationConfig()
    with path.open("rb") as handle:
        return ValidationConfig.model_validate(tomllib.load(handle))


def collector_config(path: Path) -> CollectorConfig:
    with path.open("rb") as handle:
        return CollectorConfig.model_validate(tomllib.load(handle))
