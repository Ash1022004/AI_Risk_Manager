from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
from sklearn.preprocessing import StandardScaler

from ml.features import FEATURE_COLUMNS, FEATURE_LABELS, normalize_features

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "risk_lgbm.txt"
SCALER_PATH = ROOT / "models" / "scaler.joblib"
META_PATH = ROOT / "models" / "feature_meta.json"


@lru_cache
def _booster() -> lgb.Booster:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Missing models/risk_lgbm.txt. Run: uv run python -m ml.download_and_train"
        )
    return lgb.Booster(model_file=str(MODEL_PATH))


@lru_cache
def _scaler() -> StandardScaler | None:
    if not SCALER_PATH.exists():
        return None
    return joblib.load(SCALER_PATH)


def model_ready() -> bool:
    return MODEL_PATH.exists()


def risk_band(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def score_merchant(features: dict) -> dict:
    normalized = normalize_features(features)
    raw = np.array([[normalized[name] for name in FEATURE_COLUMNS]], dtype=float)
    scaler = _scaler()
    row = scaler.transform(raw) if scaler is not None else raw
    booster = _booster()
    proba = float(booster.predict(row)[0])
    contrib = booster.predict(row, pred_contrib=True)[0]
    drivers = []
    for name, value, contribution in zip(FEATURE_COLUMNS, raw[0], contrib[:-1]):
        drivers.append(
            {
                "feature": name,
                "label": FEATURE_LABELS[name],
                "value": round(float(value), 4),
                "contribution": round(float(contribution), 4),
            }
        )
    drivers.sort(key=lambda item: abs(item["contribution"]), reverse=True)
    return {
        "risk_score": round(proba, 4),
        "risk_band": risk_band(proba),
        "feature_drivers": drivers[:8],
        "features": normalized,
    }


def model_meta() -> dict:
    if META_PATH.exists():
        return json.loads(META_PATH.read_text())
    return {}
