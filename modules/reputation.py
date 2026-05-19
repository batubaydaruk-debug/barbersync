"""Reputation Engine — algorithmic score (0-100) with event ledger."""
from __future__ import annotations
from datetime import datetime, timezone
from db.connection import get_client

# Score deltas per event type
_DELTAS: dict[str, int] = {
    "no_show":           -20,
    "late_cancel":       -10,
    "completed":          +3,
    "good_review":        +5,
    "manual_adjustment":   0,   # caller provides explicit delta
}

SCORE_MIN = 0
SCORE_MAX = 100


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: int) -> int:
    return max(SCORE_MIN, min(SCORE_MAX, value))


def apply_reputation_event(
    customer_person_id: str,
    shop_id: str | None,
    appointment_id: str | None,
    event_type: str,
    custom_delta: int | None = None,
    reason: str = "",
    performed_by: str | None = None,
) -> int:
    """Apply a reputation event, update the cached score, and return the new score."""
    sb = get_client()
    delta = custom_delta if event_type == "manual_adjustment" else _DELTAS.get(event_type, 0)

    # insert immutable ledger entry
    sb.table("reputation_events").insert({
        "customer_person_id":    customer_person_id,
        "shop_id":               shop_id,
        "appointment_id":        appointment_id,
        "event_type":            event_type,
        "score_delta":           delta,
        "reason":                reason or event_type,
        "performed_by_person_id": performed_by,
        "occurred_at":           _now(),
    }).execute()

    # update cached score
    prof = (
        sb.table("customer_profiles")
        .select("reputation_score, total_no_shows_count, total_appointments_count")
        .eq("person_id", customer_person_id)
        .execute()
        .data
    )
    if not prof:
        return 100

    current  = prof[0]["reputation_score"]
    new_score = _clamp(current + delta)
    update_payload: dict = {"reputation_score": new_score, "updated_at": _now()}

    if event_type == "no_show":
        update_payload["total_no_shows_count"] = prof[0]["total_no_shows_count"] + 1

    sb.table("customer_profiles").update(update_payload).eq("person_id", customer_person_id).execute()

    # per-shop stats
    _upsert_shop_reputation(customer_person_id, shop_id, event_type)

    return new_score


def _upsert_shop_reputation(customer_person_id: str, shop_id: str | None, event_type: str) -> None:
    if not shop_id:
        return
    sb = get_client()
    existing = (
        sb.table("customer_shop_reputations")
        .select("id, appointments_count, no_show_count")
        .eq("customer_person_id", customer_person_id)
        .eq("shop_id", shop_id)
        .execute()
        .data
    )
    if existing:
        row = existing[0]
        update: dict = {"last_event_at": _now(), "updated_at": _now()}
        if event_type == "no_show":
            update["no_show_count"] = row["no_show_count"] + 1
        if event_type == "completed":
            update["appointments_count"] = row["appointments_count"] + 1
        sb.table("customer_shop_reputations").update(update).eq("id", row["id"]).execute()
    else:
        sb.table("customer_shop_reputations").insert({
            "customer_person_id": customer_person_id,
            "shop_id":            shop_id,
            "appointments_count": 1 if event_type == "completed" else 0,
            "no_show_count":      1 if event_type == "no_show" else 0,
            "last_event_at":      _now(),
            "created_at":         _now(),
            "updated_at":         _now(),
        }).execute()


def get_reputation_profile(customer_person_id: str) -> dict:
    sb = get_client()
    rows = (
        sb.table("customer_profiles")
        .select("reputation_score, total_appointments_count, total_no_shows_count")
        .eq("person_id", customer_person_id)
        .execute()
        .data
    )
    if not rows:
        return {"reputation_score": 100, "total_appointments_count": 0, "total_no_shows_count": 0}
    p = rows[0]
    score = p["reputation_score"]
    tier  = "Yeşil" if score >= 75 else ("Sarı" if score >= 50 else "Kırmızı")
    return {
        "reputation_score":          score,
        "tier":                      tier,
        "total_appointments_count":  p["total_appointments_count"],
        "total_no_shows_count":      p["total_no_shows_count"],
    }


def get_reputation_events(customer_person_id: str, limit: int = 20) -> list[dict]:
    sb = get_client()
    return (
        sb.table("reputation_events")
        .select("event_type, score_delta, reason, occurred_at")
        .eq("customer_person_id", customer_person_id)
        .order("occurred_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )


def list_customer_reputations(shop_id: str) -> list[dict]:
    """Ranked list of customers by score for the owner's report."""
    sb = get_client()
    return (
        sb.table("customer_profiles")
        .select("person_id, reputation_score, total_appointments_count, total_no_shows_count, persons(full_name, email)")
        .order("reputation_score", desc=True)
        .limit(50)
        .execute()
        .data
    )
