from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS

TXN_COLS = [
    "TransactionID",
    "isFraud",
    "TransactionDT",
    "TransactionAmt",
    "ProductCD",
    "card1",
    "addr1",
    "addr2",
    "dist1",
    "P_emaildomain",
    "C1",
    "C2",
    "C13",
    "C14",
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
    "M6",
    "M7",
    "M8",
    "M9",
]
ID_COLS = ["TransactionID", "DeviceType", "DeviceInfo", "id_30", "id_31"]
M_COLS = [f"M{i}" for i in range(1, 10)]
FREE_EMAIL = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "aol.com",
    "mail.com",
    "protonmail.com",
    "icloud.com",
}


def _entropy(values: pd.Series) -> float:
    counts = values.dropna().astype(str).value_counts(normalize=True)
    if counts.empty:
        return 0.0
    return float(-(counts * np.log2(counts)).sum())


def reshape_ieee(data_dir: Path, min_txns: int = 8, max_merchants: int = 8000) -> pd.DataFrame:
    txn_path = data_dir / "train_transaction.csv"
    id_path = data_dir / "train_identity.csv"
    if not txn_path.exists():
        raise FileNotFoundError(f"Missing {txn_path}")

    available = pd.read_csv(txn_path, nrows=0).columns.tolist()
    usecols = [c for c in TXN_COLS if c in available]
    txn = pd.read_csv(txn_path, usecols=usecols)
    if id_path.exists():
        id_available = pd.read_csv(id_path, nrows=0).columns.tolist()
        id_usecols = [c for c in ID_COLS if c in id_available]
        identity = pd.read_csv(id_path, usecols=id_usecols)
        txn = txn.merge(identity, on="TransactionID", how="left")

    match_cols = [c for c in M_COLS if c in txn.columns and c != "M4"]
    if match_cols:
        matches = txn[match_cols].astype(str).apply(lambda col: col.str.upper().eq("T"))
        txn["kyc_mismatch"] = 1 - matches.mean(axis=1)
    else:
        txn["kyc_mismatch"] = 0.0

    txn["email_risk_row"] = (
        txn.get("P_emaildomain", pd.Series("", index=txn.index))
        .fillna("")
        .astype(str)
        .str.lower()
        .isin(FREE_EMAIL)
        .astype(float)
    )
    device_col = "DeviceInfo" if "DeviceInfo" in txn.columns else None
    if "DeviceType" in txn.columns and device_col:
        txn["device_key"] = txn["DeviceType"].astype(str) + ":" + txn[device_col].astype(str)
    elif "DeviceType" in txn.columns:
        txn["device_key"] = txn["DeviceType"].astype(str)
    else:
        txn["device_key"] = "unknown"

    grouped = []
    for card, part in txn.groupby("card1"):
        if len(part) < min_txns:
            continue
        part = part.sort_values("TransactionDT")
        split = max(len(part) // 2, 1)
        early_amt = part["TransactionAmt"].iloc[:split].sum()
        late_amt = part["TransactionAmt"].iloc[split:].sum()
        spike = float(late_amt / early_amt) if early_amt > 0 else float(late_amt > 0)
        addr_nunique = part["addr1"].nunique(dropna=True) if "addr1" in part else 1
        grouped.append(
            {
                "merchant_key": str(card),
                "kyc_mismatch_rate": float(part["kyc_mismatch"].mean()),
                "volume_spike": min(spike, 12.0),
                "chargeback_ratio": float(part["isFraud"].mean()),
                "ticket_amt_mean": float(part["TransactionAmt"].mean()),
                "ticket_amt_std": float(part["TransactionAmt"].std() or 0.0),
                "ticket_amt_p95": float(part["TransactionAmt"].quantile(0.95)),
                "txn_count": float(len(part)),
                "device_anomaly": min(part["device_key"].nunique() / max(len(part), 1), 1.0),
                "ip_geo_anomaly": min(addr_nunique / 8.0, 1.0),
                "email_risk": float(part["email_risk_row"].mean()),
                "product_mix_entropy": _entropy(part["ProductCD"]) if "ProductCD" in part else 0.0,
                "unique_devices": float(part["device_key"].nunique()),
                "unique_emails": float(part["P_emaildomain"].nunique(dropna=True))
                if "P_emaildomain" in part
                else 1.0,
                "is_risky": int(part["isFraud"].mean() >= 0.05 or part["isFraud"].sum() >= 3),
            }
        )
        if len(grouped) >= max_merchants:
            break

    frame = pd.DataFrame(grouped)
    if frame.empty:
        raise ValueError("IEEE-CIS reshape produced no merchants — check the CSVs.")
    return frame[FEATURE_COLUMNS + ["is_risky", "merchant_key"]]
