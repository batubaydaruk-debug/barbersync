"""Reservation Management module — booking, slots, photos, status transitions."""
from __future__ import annotations
import base64
from datetime import datetime, timedelta, timezone, date, time
from db.connection import get_client
from utils.tz import TZ_TR

BOOKING_MIN_SCORE = 40          # reputation score below this blocks new bookings
SLOT_START_HOUR   = 9           # shop opens 09:00
SLOT_END_HOUR     = 19          # shop closes 19:00
SLOT_INTERVAL     = 30          # slot granularity in minutes


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- shop & barber lookup ---------------------------------------------

def list_shops() -> list[dict]:
    sb = get_client()
    return (
        sb.table("shops")
        .select("id, display_name, city, address_line1")
        .eq("is_active", True)
        .eq("is_accepting_appointments", True)
        .is_("deleted_at", "null")
        .execute()
        .data
    )


def list_barbers(shop_id: str) -> list[dict]:
    """Return barbers with their person name for a given shop."""
    sb = get_client()
    profiles = (
        sb.table("barber_profiles")
        .select("id, person_id, display_name")
        .eq("shop_id", shop_id)
        .eq("is_active", True)
        .eq("is_accepting_appointments", True)
        .is_("deleted_at", "null")
        .execute()
        .data
    )
    return profiles


def list_services(shop_id: str, barber_profile_id: str | None = None) -> list[dict]:
    """Return active services for a shop, optionally filtered by barber."""
    sb = get_client()
    if barber_profile_id:
        bs = (
            sb.table("barber_services")
            .select("service_id, override_price, override_duration_minutes, services(id,name,default_duration_minutes,base_price)")
            .eq("barber_profile_id", barber_profile_id)
            .eq("is_active", True)
            .execute()
            .data
        )
        result = []
        for row in bs:
            svc = row.get("services") or {}
            result.append({
                "id":               svc.get("id"),
                "name":             svc.get("name"),
                "duration_minutes": row["override_duration_minutes"] or svc.get("default_duration_minutes", 30),
                "price":            float(row["override_price"] or svc.get("base_price", 0)),
            })
        return result
    # all shop services
    return (
        sb.table("services")
        .select("id, name, default_duration_minutes, base_price")
        .eq("shop_id", shop_id)
        .eq("is_active", True)
        .is_("deleted_at", "null")
        .execute()
        .data
    )


# ---------- availability -----------------------------------------------------

def get_available_slots(
    barber_person_id: str,
    target_date: date,
    duration_min: int = 30,
) -> list[datetime]:
    """Return list of available UTC datetimes for a barber on a given date."""
    sb = get_client()

    day_start = datetime.combine(target_date, time(SLOT_START_HOUR, 0), tzinfo=TZ_TR)
    day_end   = datetime.combine(target_date, time(SLOT_END_HOUR,   0), tzinfo=TZ_TR)

    booked = (
        sb.table("appointments")
        .select("scheduled_start, scheduled_end")
        .eq("barber_person_id", barber_person_id)
        .gte("scheduled_start", day_start.isoformat())
        .lte("scheduled_start", day_end.isoformat())
        .not_.in_("status", ["cancelled_by_customer", "cancelled_by_shop"])
        .execute()
        .data
    )

    busy_intervals = [
        (
            datetime.fromisoformat(r["scheduled_start"]),
            datetime.fromisoformat(r["scheduled_end"]),
        )
        for r in booked
    ]

    slots = []
    cursor = day_start
    while cursor + timedelta(minutes=duration_min) <= day_end:
        end = cursor + timedelta(minutes=duration_min)
        if not any(s < end and cursor < e for s, e in busy_intervals):
            slots.append(cursor)
        cursor += timedelta(minutes=SLOT_INTERVAL)
    return slots


# ---------- booking ----------------------------------------------------------

def check_booking_allowed(customer_person_id: str) -> tuple[bool, int]:
    """Return (allowed, current_score)."""
    sb = get_client()
    rows = (
        sb.table("customer_profiles")
        .select("reputation_score")
        .eq("person_id", customer_person_id)
        .execute()
        .data
    )
    score = rows[0]["reputation_score"] if rows else 100
    return score >= BOOKING_MIN_SCORE, score


def create_appointment(
    shop_id: str,
    customer_person_id: str,
    barber_person_id: str,
    service_id: str,
    scheduled_start: datetime,
    duration_min: int,
    price: float,
    customer_notes: str = "",
) -> dict:
    sb = get_client()

    allowed, score = check_booking_allowed(customer_person_id)
    if not allowed:
        raise ValueError(
            f"İtibar puanınız ({score}) yeterli değil. "
            f"Randevu alabilmek için en az {BOOKING_MIN_SCORE} puan gerekiyor."
        )

    scheduled_end = scheduled_start + timedelta(minutes=duration_min)

    appt = sb.table("appointments").insert({
        "shop_id":              shop_id,
        "customer_person_id":  customer_person_id,
        "barber_person_id":    barber_person_id,
        "status":              "confirmed",
        "scheduled_start":     scheduled_start.isoformat(),
        "scheduled_end":       scheduled_end.isoformat(),
        "total_price_snapshot": price,
        "customer_notes":      customer_notes,
        "created_at": _now(),
        "updated_at": _now(),
    }).execute().data[0]

    appt_id = appt["id"]

    # service link
    sb.table("appointment_services").insert({
        "appointment_id":          appt_id,
        "service_id":              service_id,
        "duration_minutes_snapshot": duration_min,
        "display_order":           0,
    }).execute()

    # status history
    sb.table("appointment_status_history").insert({
        "appointment_id":       appt_id,
        "shop_id":              shop_id,
        "to_status":            "confirmed",
        "changed_by_person_id": customer_person_id,
        "changed_at":           _now(),
    }).execute()

    # update customer profile counter
    sb.rpc("increment_customer_appointment_count", {"p_person_id": customer_person_id}).execute()

    # in-app notification for barber
    sb.table("notifications").insert({
        "shop_id":              shop_id,
        "recipient_person_id":  barber_person_id,
        "template_key":         "new_appointment",
        "channel":              "in_app",
        "status":               "sent",
        "related_entity_type":  "appointment",
        "related_entity_id":    appt_id,
        "payload":              {"scheduled_start": scheduled_start.isoformat()},
        "delivered_at":         _now(),
        "created_at":           _now(),
    }).execute()

    return appt


def upload_reference_photo(
    appointment_id: str,
    shop_id: str,
    person_id: str,
    image_bytes: bytes,
    file_name: str = "photo.jpg",
) -> str:
    """Upload photo to Supabase Storage and record URI. Returns storage URI."""
    sb = get_client()

    path = f"{shop_id}/{appointment_id}/{file_name}"
    try:
        sb.storage.from_("haircut-photos").upload(
            path,
            image_bytes,
            {"content-type": "image/jpeg", "upsert": "true"},
        )
        uri = sb.storage.from_("haircut-photos").get_public_url(path)
    except Exception:
        # Fallback: store base64 inline URI for demo/dev environments
        b64 = base64.b64encode(image_bytes).decode()
        uri = f"data:image/jpeg;base64,{b64[:80]}..."

    from datetime import timedelta
    retain_until = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()

    sb.table("appointment_reference_images").insert({
        "appointment_id":       appointment_id,
        "shop_id":              shop_id,
        "storage_uri":          uri,
        "file_type":            file_name.rsplit(".", 1)[-1].upper(),
        "uploaded_by_person_id": person_id,
        "uploaded_at":          _now(),
        "retain_until":         retain_until,
        "created_at":           _now(),
        "updated_at":           _now(),
    }).execute()

    return uri


def get_reference_images(appointment_id: str) -> list[dict]:
    sb = get_client()
    return (
        sb.table("appointment_reference_images")
        .select("storage_uri, file_type, uploaded_at")
        .eq("appointment_id", appointment_id)
        .execute()
        .data
    )


# ---------- customer view ----------------------------------------------------

def get_customer_appointments(customer_person_id: str) -> list[dict]:
    sb = get_client()
    return (
        sb.table("appointments")
        .select(
            "id, status, scheduled_start, scheduled_end, total_price_snapshot, customer_notes,"
            "shops(display_name), persons!barber_person_id(full_name)"
        )
        .eq("customer_person_id", customer_person_id)
        .order("scheduled_start", desc=True)
        .limit(20)
        .execute()
        .data
    )


# ---------- barber view ------------------------------------------------------

def get_barber_appointments(barber_person_id: str, target_date: date) -> list[dict]:
    sb = get_client()
    day_start = datetime.combine(target_date, time(0, 0), tzinfo=timezone.utc)
    day_end   = datetime.combine(target_date, time(23, 59), tzinfo=timezone.utc)
    return (
        sb.table("appointments")
        .select(
            "id, status, scheduled_start, scheduled_end, total_price_snapshot, customer_notes,"
            "persons!customer_person_id(full_name),"
            "appointment_services(duration_minutes_snapshot, services(name))"
        )
        .eq("barber_person_id", barber_person_id)
        .gte("scheduled_start", day_start.isoformat())
        .lte("scheduled_start", day_end.isoformat())
        .order("scheduled_start")
        .execute()
        .data
    )


# ---------- status transitions -----------------------------------------------

def update_appointment_status(
    appointment_id: str,
    new_status: str,
    changed_by: str,
    reason: str = "",
) -> None:
    sb = get_client()
    old = sb.table("appointments").select("status, shop_id, customer_person_id").eq("id", appointment_id).execute().data
    old_status = old[0]["status"] if old else None
    shop_id    = old[0]["shop_id"] if old else None
    customer_id = old[0]["customer_person_id"] if old else None

    sb.table("appointments").update({
        "status":     new_status,
        "updated_at": _now(),
    }).eq("id", appointment_id).execute()

    if shop_id:
        sb.table("appointment_status_history").insert({
            "appointment_id":       appointment_id,
            "shop_id":              shop_id,
            "from_status":          old_status,
            "to_status":            new_status,
            "changed_by_person_id": changed_by,
            "reason":               reason,
            "changed_at":           _now(),
        }).execute()

    # reputation side-effects handled in reputation module
    if new_status == "no_show" and customer_id:
        from modules.reputation import apply_reputation_event
        apply_reputation_event(customer_id, shop_id, appointment_id, "no_show")
    elif new_status == "completed" and customer_id:
        from modules.reputation import apply_reputation_event
        apply_reputation_event(customer_id, shop_id, appointment_id, "completed")
    elif new_status == "late_cancel" and customer_id:
        from modules.reputation import apply_reputation_event
        apply_reputation_event(customer_id, shop_id, appointment_id, "late_cancel")


def submit_review(
    appointment_id: str,
    shop_id: str,
    barber_person_id: str,
    reviewer_person_id: str,
    rating: int,
    comment: str = "",
) -> None:
    sb = get_client()
    sb.table("reviews").insert({
        "appointment_id":    appointment_id,
        "shop_id":           shop_id,
        "barber_person_id":  barber_person_id,
        "reviewer_person_id": reviewer_person_id,
        "rating":            rating,
        "comment":           comment,
        "submitted_at":      _now(),
        "created_at":        _now(),
        "updated_at":        _now(),
    }).execute()

    if rating >= 4:
        from modules.reputation import apply_reputation_event
        apply_reputation_event(reviewer_person_id, shop_id, appointment_id, "good_review")
