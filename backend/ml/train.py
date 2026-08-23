from __future__ import annotations

import json
from pathlib import Path

import joblib
import lightgbm as lgb
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from ml.features import FEATURE_COLUMNS

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
DATA_DIR = ROOT / "data"


def train_model(frame: pd.DataFrame, source: str) -> dict:
    X = frame[FEATURE_COLUMNS]
    y = frame["is_risky"].astype(int)
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train.to_numpy())
    X_val_s = scaler.transform(X_val.to_numpy())
    model = lgb.LGBMClassifier(
        n_estimators=240,
        learning_rate=0.05,
        num_leaves=31,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_samples=20,
        random_state=42,
        verbosity=-1,
    )
    model.fit(X_train_s, y_train)
    val_prob = model.predict_proba(X_val_s)[:, 1]
    auc = float(roc_auc_score(y_val, val_prob)) if y_val.nunique() > 1 else 0.0

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(MODELS_DIR / "risk_lgbm.txt"))
    joblib.dump(scaler, MODELS_DIR / "scaler.joblib")
    meta = {
        "features": FEATURE_COLUMNS,
        "source": source,
        "scaled": True,
        "auc": auc,
        "n_rows": int(len(frame)),
        "positive_rate": float(y.mean()),
    }
    (MODELS_DIR / "feature_meta.json").write_text(json.dumps(meta, indent=2))
    frame.to_parquet(DATA_DIR / "merchants.parquet", index=False)
    return meta
