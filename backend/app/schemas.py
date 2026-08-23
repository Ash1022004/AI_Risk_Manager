from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Action = Literal["approve", "hold", "escalate"]
ReviewStatus = Literal["queued", "scoring", "agent_reviewing", "decided", "overridden", "failed"]


class FeaturePayload(BaseModel):
    kyc_mismatch_rate: float = 0.0
    volume_spike: float = 0.0
    chargeback_ratio: float = 0.0
    ticket_amt_mean: float = 0.0
    ticket_amt_std: float = 0.0
    ticket_amt_p95: float = 0.0
    txn_count: float = 0.0
    device_anomaly: float = 0.0
    ip_geo_anomaly: float = 0.0
    email_risk: float = 0.0
    product_mix_entropy: float = 0.0
    unique_devices: float = 0.0
    unique_emails: float = 0.0


class MerchantCreate(BaseModel):
    name: str
    category: str | None = "general"
    features: FeaturePayload = Field(default_factory=FeaturePayload)
    source: str = "manual"


class MerchantOut(BaseModel):
    id: str
    name: str
    category: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    source: str | None = None
    created_at: datetime | str | None = None


class ReviewCreate(BaseModel):
    merchant_id: str | None = None
    seed: str | None = None
    merchant: MerchantCreate | None = None


class OverrideBody(BaseModel):
    action: Action
    note: str | None = None


class ReviewOut(BaseModel):
    id: str
    merchant_id: str | None = None
    merchant: MerchantOut | None = None
    status: str
    risk_score: float | None = None
    risk_band: str | None = None
    recommended_action: str | None = None
    explanation: str | None = None
    feature_drivers: list[dict[str, Any]] = Field(default_factory=list)
    policy_hits: list[dict[str, Any]] = Field(default_factory=list)
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)
    human_action: str | None = None
    human_note: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
