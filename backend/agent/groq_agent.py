from __future__ import annotations

import json
import os
from typing import Any, Callable

import dotenv
from groq import Groq

from agent.policy import enforce_floor, evaluate_policy
from app.config import get_settings

dotenv.load_dotenv()

_groq_state = {"status": "unknown", "detail": None}


def groq_status() -> dict[str, str | None]:
    return dict(_groq_state)


def _public_groq_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if "invalid_api_key" in lowered or "401" in text:
        return "Groq rejected GROQ_API_KEY. LightGBM + policy still decided this case."
    return text[:240]


def _client() -> tuple[Groq, str]:
    dotenv.load_dotenv(override=True)
    get_settings.cache_clear()
    settings = get_settings()
    api_key = os.environ.get("GROQ_API_KEY") or settings.groq_api_key
    model = os.environ.get("GROQ_MODEL") or settings.groq_model
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is empty")
    return Groq(api_key=api_key), model


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_merchant_profile",
            "description": "Return the merchant KYC and transaction-signal snapshot.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk_score",
            "description": "Return the LightGBM risk score and band.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_feature_drivers",
            "description": "Return the top SHAP-style feature contributions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_policy",
            "description": "Return deterministic policy hits and the minimum allowed action.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_similar_merchants",
            "description": "Find similar historical merchant profiles.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

SYSTEM_PROMPT = """You are a Razorpay-style merchant risk reviewer (a scoped Bumblebee).
You do not invent a risk score. Call tools to read the LightGBM score, feature drivers, policy, and similar merchants.
Then recommend exactly one action: approve, hold, or escalate.
Policy is a hard guardrail: you cannot recommend a weaker action than lookup_policy.action_floor.
Write 3-6 sentences a human analyst can put in an audit trail. Cite the concrete drivers (KYC, volume spike, chargebacks, device/IP).
When you are done, reply with ONLY valid JSON:
{"action":"approve|hold|escalate","explanation":"..."}
"""


def _parse_decision(content: str) -> dict[str, str] | None:
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    action = str(data.get("action", "")).lower()
    explanation = str(data.get("explanation", "")).strip()
    if action not in {"approve", "hold", "escalate"} or not explanation:
        return None
    return {"action": action, "explanation": explanation}


def _fallback_explanation(score: dict[str, Any], policy: dict[str, Any]) -> str:
    top = ", ".join(
        f"{d['label']} ({d['value']})" for d in (score.get("feature_drivers") or [])[:3]
    )
    hits = "; ".join(hit["message"] for hit in policy.get("hits") or [])
    return (
        f"Model score {score.get('risk_score')} ({score.get('risk_band')} band). "
        f"Top drivers: {top or 'none'}. Policy: {hits or 'no hard rules'}. "
        f"Recommended action is {policy.get('action_floor')} under the policy floor."
    )


def _tool_payload(message: Any) -> dict[str, Any]:
    tool_calls = []
    for call in message.tool_calls or []:
        tool_calls.append(
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments or "{}",
                },
            }
        )
    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": tool_calls,
    }


def review_case(
    *,
    merchant: dict[str, Any],
    score: dict[str, Any],
    similar: list[dict[str, Any]],
) -> dict[str, Any]:
    features = score.get("features") or merchant.get("features") or {}
    policy = evaluate_policy(features, float(score.get("risk_score") or 0))
    trace: list[dict[str, Any]] = []

    tool_impls: dict[str, Callable[[], Any]] = {
        "get_merchant_profile": lambda: {
            "id": merchant.get("id"),
            "name": merchant.get("name"),
            "category": merchant.get("category"),
            "features": features,
        },
        "get_risk_score": lambda: {
            "risk_score": score.get("risk_score"),
            "risk_band": score.get("risk_band"),
        },
        "get_feature_drivers": lambda: score.get("feature_drivers") or [],
        "lookup_policy": lambda: policy,
        "search_similar_merchants": lambda: similar,
    }

    try:
        client, model = _client()
    except Exception as exc:
        _groq_state.update({"status": "missing", "detail": str(exc)})
        return {
            "recommended_action": policy["action_floor"],
            "explanation": _fallback_explanation(score, policy),
            "policy_hits": policy["hits"],
            "agent_trace": [{"type": "fallback", "reason": str(exc)}],
        }

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Review merchant '{merchant.get('name')}'. "
                "Call the tools you need, then return the JSON decision."
            ),
        },
    ]

    try:
        for _ in range(8):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            message = response.choices[0].message
            if message.tool_calls:
                messages.append(_tool_payload(message))
                for call in message.tool_calls:
                    name = call.function.name
                    impl = tool_impls.get(name)
                    result = impl() if impl else {"error": f"unknown tool {name}"}
                    trace.append({"type": "tool", "name": name, "result": result})
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(result, default=str),
                        }
                    )
                continue

            decision = _parse_decision(message.content or "")
            if not decision:
                json_response = client.chat.completions.create(
                    model=model,
                    messages=messages
                    + [
                        {
                            "role": "user",
                            "content": 'Return only JSON: {"action":"approve|hold|escalate","explanation":"..."}',
                        }
                    ],
                    response_format={"type": "json_object"},
                )
                decision = _parse_decision(json_response.choices[0].message.content or "")
            if decision:
                _groq_state.update({"status": "ok", "detail": None})
                action = enforce_floor(decision["action"], policy["action_floor"])
                explanation = decision["explanation"]
                if action != decision["action"]:
                    explanation += (
                        f" Policy floor raised this from {decision['action']} to {action}."
                    )
                    trace.append({"type": "policy_override", "from": decision["action"], "to": action})
                return {
                    "recommended_action": action,
                    "explanation": explanation,
                    "policy_hits": policy["hits"],
                    "agent_trace": trace,
                }
            break
    except Exception as exc:
        public = _public_groq_error(exc)
        _groq_state.update({"status": "error", "detail": public})
        trace.append({"type": "error", "message": public})

    action = policy["action_floor"]
    return {
        "recommended_action": action,
        "explanation": _fallback_explanation(score, policy),
        "policy_hits": policy["hits"],
        "agent_trace": trace + [{"type": "fallback", "reason": "agent_unstructured"}],
    }
