FEATURE_COLUMNS = [
    "kyc_mismatch_rate",
    "volume_spike",
    "chargeback_ratio",
    "ticket_amt_mean",
    "ticket_amt_std",
    "ticket_amt_p95",
    "txn_count",
    "device_anomaly",
    "ip_geo_anomaly",
    "email_risk",
    "product_mix_entropy",
    "unique_devices",
    "unique_emails",
]

FEATURE_LABELS = {
    "kyc_mismatch_rate": "KYC mismatch rate",
    "volume_spike": "Volume spike vs baseline",
    "chargeback_ratio": "Chargeback / fraud ratio",
    "ticket_amt_mean": "Mean ticket size",
    "ticket_amt_std": "Ticket size volatility",
    "ticket_amt_p95": "P95 ticket size",
    "txn_count": "Transaction count",
    "device_anomaly": "Device fingerprint anomaly",
    "ip_geo_anomaly": "IP / geo inconsistency",
    "email_risk": "Email domain risk",
    "product_mix_entropy": "Product mix entropy",
    "unique_devices": "Unique devices",
    "unique_emails": "Unique emails",
}


def default_features() -> dict[str, float]:
    return {name: 0.0 for name in FEATURE_COLUMNS}


def normalize_features(raw: dict | None) -> dict[str, float]:
    features = default_features()
    if not raw:
        return features
    for name in FEATURE_COLUMNS:
        try:
            features[name] = float(raw.get(name, 0.0) or 0.0)
        except (TypeError, ValueError):
            features[name] = 0.0
    return features
