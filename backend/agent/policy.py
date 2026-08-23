from __future__ import annotations

from typing import Any


def evaluate_policy(features: dict[str, Any], risk_score: float) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    floor: str | None = None

    def hit(code: str, severity: str, message: str, action_floor: str) -> None:
        nonlocal floor
        hits.append({"code": code, "severity": severity, "message": message, "action_floor": action_floor})
        order = {"approve": 0, "hold": 1, "escalate": 2}
        if floor is None or order[action_floor] > order[floor]:
            floor = action_floor

    kyc = float(features.get("kyc_mismatch_rate") or 0)
    chargeback = float(features.get("chargeback_ratio") or 0)
    spike = float(features.get("volume_spike") or 0)

    if kyc >= 0.5:
        hit("kyc_hard_fail", "high", "KYC mismatch rate is at or above 50%.", "escalate")
    if chargeback >= 0.05:
        hit("chargeback_critical", "high", "Chargeback/fraud ratio is at or above 5%.", "escalate")
    elif chargeback >= 0.02:
        hit("chargeback_elevated", "medium", "Chargeback/fraud ratio is at or above 2%.", "hold")
    if spike >= 4:
        hit("volume_spike", "medium", "Recent volume is 4x+ the earlier baseline.", "hold")
    if risk_score >= 0.75:
        hit("model_high", "high", "LightGBM risk score is in the high band.", "escalate")
    elif risk_score >= 0.4:
        hit("model_medium", "medium", "LightGBM risk score is in the medium band.", "hold")

    if floor is None:
        if risk_score < 0.2 and kyc < 0.2 and chargeback < 0.01:
            floor = "approve"
            hits.append(
                {
                    "code": "clean_profile",
                    "severity": "low",
                    "message": "Low model score with clean KYC and chargeback profile.",
                    "action_floor": "approve",
                }
            )
        else:
            floor = "hold"
            hits.append(
                {
                    "code": "default_hold",
                    "severity": "low",
                    "message": "No hard fail, but the profile is not clean enough to auto-approve.",
                    "action_floor": "hold",
                }
            )

    return {"hits": hits, "action_floor": floor}


def enforce_floor(recommended: str, action_floor: str) -> str:
    order = {"approve": 0, "hold": 1, "escalate": 2}
    if recommended not in order:
        return action_floor
    return recommended if order[recommended] >= order[action_floor] else action_floor
