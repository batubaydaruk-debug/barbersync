"""Google Gemini API — AI-powered no-show probability prediction (R07)."""
from __future__ import annotations
import os
import re
from dotenv import load_dotenv

load_dotenv()

_MODEL_VERSION = "gemini-1.5-flash"


def _heuristic_prediction(
    reputation_score: int,
    no_show_rate: float,
    days_ahead: int,
    day_of_week: int,       # 0=Mon … 6=Sun
    service_duration: int,  # minutes
) -> float:
    """Rule-based fallback when Gemini API key is unavailable."""
    p = 0.10
    if reputation_score < 40:
        p += 0.35
    elif reputation_score < 60:
        p += 0.20
    elif reputation_score < 80:
        p += 0.08

    p += min(no_show_rate * 0.5, 0.30)

    if days_ahead == 0:
        p -= 0.05
    elif days_ahead >= 7:
        p += 0.10

    if day_of_week == 0:   # Monday
        p += 0.05

    if service_duration > 60:
        p -= 0.05

    return round(max(0.0, min(1.0, p)), 3)


def predict_noshow(
    reputation_score: int,
    no_show_rate: float,
    days_ahead: int,
    day_of_week: int,
    service_duration: int,
) -> tuple[float, str]:
    """Return (probability, model_version). Falls back to heuristic if no API key."""
    api_key = os.getenv("GEMINI_API_KEY", "")

    if not api_key:
        prob = _heuristic_prediction(
            reputation_score, no_show_rate, days_ahead, day_of_week, service_duration
        )
        return prob, "heuristic-v1"

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(_MODEL_VERSION)

        prompt = f"""
You are a no-show prediction model for a Turkish barbershop system.

Given these appointment features, output ONLY a single decimal number between 0.00 and 1.00
representing the probability that the customer will NOT show up.

Features:
- Customer reputation score: {reputation_score}/100  (100 = perfect history)
- Customer historical no-show rate: {no_show_rate:.2%}
- Days until appointment: {days_ahead}
- Day of week: {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day_of_week]}
- Service duration: {service_duration} minutes

Return ONLY the number, nothing else.
"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        match = re.search(r"0?\.\d+|\d+\.\d+", text)
        if match:
            prob = float(match.group())
            prob = max(0.0, min(1.0, prob))
            return round(prob, 3), _MODEL_VERSION
    except Exception:
        pass

    prob = _heuristic_prediction(
        reputation_score, no_show_rate, days_ahead, day_of_week, service_duration
    )
    return prob, "heuristic-v1 (fallback)"


def store_prediction(appointment_id: str, probability: float, model_version: str, features: dict) -> None:
    """Persist the prediction to the noshow_predictions table."""
    from db.connection import get_client
    from datetime import datetime, timezone
    sb = get_client()
    now = datetime.now(timezone.utc).isoformat()
    existing = sb.table("noshow_predictions").select("id").eq("appointment_id", appointment_id).execute().data
    if existing:
        sb.table("noshow_predictions").update({
            "predicted_probability": probability,
            "model_version":         model_version,
            "feature_snapshot":      features,
            "updated_at":            now,
        }).eq("id", existing[0]["id"]).execute()
    else:
        sb.table("noshow_predictions").insert({
            "appointment_id":       appointment_id,
            "predicted_probability": probability,
            "model_version":        model_version,
            "feature_snapshot":     features,
            "created_at":           now,
            "updated_at":           now,
        }).execute()
