from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS


def generate_synthetic_merchants(n: int = 4000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    risky = rng.random(n) < 0.22

    kyc = np.where(risky, rng.beta(4, 2, n), rng.beta(1.4, 6, n))
    spike = np.where(risky, rng.gamma(4.0, 0.9, n), rng.gamma(1.2, 0.35, n))
    chargeback = np.where(risky, rng.beta(3.5, 6, n), rng.beta(1.1, 40, n))
    mean_ticket = np.where(risky, rng.lognormal(5.4, 0.8, n), rng.lognormal(4.4, 0.45, n))
    std_ticket = mean_ticket * rng.uniform(0.15, 0.9, n)
    p95_ticket = mean_ticket * rng.uniform(1.4, 3.8, n)
    txn_count = np.where(risky, rng.integers(8, 420, n), rng.integers(12, 180, n)).astype(float)
    device = np.where(risky, rng.beta(4, 2.2, n), rng.beta(1.3, 7, n))
    geo = np.where(risky, rng.beta(3.8, 2.5, n), rng.beta(1.2, 8, n))
    email = np.where(risky, rng.beta(3.2, 2.8, n), rng.beta(1.4, 6, n))
    entropy = np.clip(rng.normal(1.1, 0.45, n) + risky * 0.6, 0, 3)
    uniq_dev = np.clip(rng.integers(1, 8, n) + risky * rng.integers(0, 4, n), 1, 12).astype(float)
    uniq_email = np.clip(rng.integers(1, 4, n) + risky * rng.integers(0, 3, n), 1, 8).astype(float)

    # A few noisy labels so the model is not a perfect rule dump.
    flip = rng.random(n) < 0.04
    label = risky ^ flip

    frame = pd.DataFrame(
        {
            "kyc_mismatch_rate": np.clip(kyc, 0, 1),
            "volume_spike": np.clip(spike, 0, 12),
            "chargeback_ratio": np.clip(chargeback, 0, 1),
            "ticket_amt_mean": mean_ticket,
            "ticket_amt_std": std_ticket,
            "ticket_amt_p95": p95_ticket,
            "txn_count": txn_count,
            "device_anomaly": np.clip(device, 0, 1),
            "ip_geo_anomaly": np.clip(geo, 0, 1),
            "email_risk": np.clip(email, 0, 1),
            "product_mix_entropy": entropy,
            "unique_devices": uniq_dev,
            "unique_emails": uniq_email,
            "is_risky": label.astype(int),
        }
    )
    return frame[FEATURE_COLUMNS + ["is_risky"]]
