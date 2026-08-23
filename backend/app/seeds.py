SEED_MERCHANTS = [
    {
        "slug": "high-risk",
        "name": "NovaGadget Hub",
        "category": "electronics",
        "source": "seed",
        "features": {
            "kyc_mismatch_rate": 0.72,
            "volume_spike": 6.4,
            "chargeback_ratio": 0.081,
            "ticket_amt_mean": 842.0,
            "ticket_amt_std": 510.0,
            "ticket_amt_p95": 2100.0,
            "txn_count": 186,
            "device_anomaly": 0.71,
            "ip_geo_anomaly": 0.66,
            "email_risk": 0.64,
            "product_mix_entropy": 1.9,
            "unique_devices": 5,
            "unique_emails": 3,
        },
    },
    {
        "slug": "clean",
        "name": "Maple Grocery Co",
        "category": "grocery",
        "source": "seed",
        "features": {
            "kyc_mismatch_rate": 0.04,
            "volume_spike": 1.1,
            "chargeback_ratio": 0.002,
            "ticket_amt_mean": 28.5,
            "ticket_amt_std": 9.2,
            "ticket_amt_p95": 46.0,
            "txn_count": 94,
            "device_anomaly": 0.08,
            "ip_geo_anomaly": 0.05,
            "email_risk": 0.12,
            "product_mix_entropy": 0.4,
            "unique_devices": 2,
            "unique_emails": 1,
        },
    },
    {
        "slug": "borderline",
        "name": "Orbit Fitness Pass",
        "category": "subscriptions",
        "source": "seed",
        "features": {
            "kyc_mismatch_rate": 0.21,
            "volume_spike": 2.8,
            "chargeback_ratio": 0.027,
            "ticket_amt_mean": 149.0,
            "ticket_amt_std": 38.0,
            "ticket_amt_p95": 199.0,
            "txn_count": 61,
            "device_anomaly": 0.33,
            "ip_geo_anomaly": 0.22,
            "email_risk": 0.41,
            "product_mix_entropy": 0.9,
            "unique_devices": 5,
            "unique_emails": 3,
        },
    },
]


def get_seed(slug: str) -> dict | None:
    for item in SEED_MERCHANTS:
        if item["slug"] == slug:
            return item
    return None
