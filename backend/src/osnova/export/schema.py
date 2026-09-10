# src/osnova/export/schema.py
"""Mirror of frontend/src/lib/types.ts plus additive fields. Field names are camelCase on purpose."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from osnova.config import ASSET_FE_KEY

EventType = Literal["ev_charging", "pv_generation", "heat_pump_heating", "battery_cycle", "high_consumption"]
AssetKey = Literal["pv", "battery", "heatPump", "ev"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetPrediction(_Strict):
    pv: int = Field(ge=0, le=100)
    battery: int = Field(ge=0, le=100)
    heatPump: int = Field(ge=0, le=100)  # noqa: N815 - FE key
    ev: int = Field(ge=0, le=100)


class ElectricityPoint(_Strict):
    timestamp: str  # ISO 8601 with offset
    powerKw: float  # noqa: N815 - net power, negative = export


class BuildingEvent(_Strict):
    type: EventType
    start: str
    end: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class ShapFeature(_Strict):
    feature: str
    contribution: float


class AssetExplanation(_Strict):
    reasons: list[str]
    shap: list[ShapFeature]


class BuildingExplanation(_Strict):
    model: str
    inputs: list[str]
    additionalData: list[str]  # noqa: N815
    method: str
    methodDescription: str  # noqa: N815
    assets: dict[AssetKey, AssetExplanation]


class GroundTruth(_Strict):
    pv: bool | None = None
    battery: bool | None = None
    heatPump: bool | None = None  # noqa: N815
    ev: bool | None = None


class YearPrediction(_Strict):
    year: int
    predictions: AssetPrediction


class Building(_Strict):
    id: str
    postcode: str
    city: str
    canton: str
    predictions: AssetPrediction
    electricity: list[ElectricityPoint]
    events: list[BuildingEvent]
    explanation: BuildingExplanation
    # additive fields, ignored by the FE until it opts in
    featured: bool = False
    profileDate: str | None = None  # noqa: N815
    groundTruth: GroundTruth | None = None  # noqa: N815
    history: list[YearPrediction] = Field(default_factory=list)


class BuildingsFile(RootModel[list[Building]]):
    pass


def to_fe_predictions(probs: dict[str, float]) -> AssetPrediction:
    """{'pv': 0.92, 'heat_pump': 0.31, ...} -> AssetPrediction with FE keys and 0-100 ints."""
    return AssetPrediction(
        **{ASSET_FE_KEY[k]: int(round(max(0.0, min(1.0, v)) * 100)) for k, v in probs.items()}
    )
