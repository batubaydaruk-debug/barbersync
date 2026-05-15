from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import bcrypt
import streamlit as st
from supabase import Client, create_client


# ── Client ─────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _naive(ts: str) -> datetime:
    """Parse an ISO timestamp from Supabase and return a timezone-naive datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)


# ── Auth ───────────────────────────────────────────────────────────────────────

def login_user(email: str, password: str):
    sb = get_supabase()
    res = (
        sb.table("persons")
        .select("*")
        .eq("email", email)
        .is_("deleted_at", "null")
        .execute()
    )
    if not res.data:
        return None, "E-posta bulunamadı."
    user = res.data[0]
    if not _verify(password, user["password_hash"]):
        return None, "Hatalı şifre."
    return user, None


def register_user(full_name: str, email: str, phone: str, password: str, role: str):
    sb = get_supabase()
    existing = (
        sb.table("persons")
        .select("id")
        .or_(f"email.eq.{email},phone.eq.{phone}")
        .execute()
    )
    if existing.data:
        return None, "Bu e-posta veya telefon zaten kayıtlı."
    res = sb.table("persons").insert({
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "password_hash": _hash(password),
        "role": role,
    }).execute()
    if res.data:
        return res.data[0], None
    return None, "Kayıt sırasında hata oluştu."


# ── Shops ──────────────────────────────────────────────────────────────────────

def list_shops() -> list[dict]:
    sb = get_supabase()
    return (
        sb.table("shops")
        .select("id, display_name, phone, address")
        .eq("is_active", True)
        .order("display_name")
        .execute()
        .data or []
    )


def get_or_create_shop_for_owner(owner_person_id: str, display_name: str) -> dict:
    sb = get_supabase()
    res = sb.table("shops").select("*").eq("owner_person_id", owner_person_id).execute()
    if res.data:
        return res.data[0]
    res = sb.table("shops").insert({
        "owner_person_id": owner_person_id,
        "display_name": display_name,
        "is_active": True,
    }).execute()
    return res.data[0]


# ── Barbers ────────────────────────────────────────────────────────────────────

def list_barbers(shop_id: str) -> list[dict]:
    """Returns available barbers for a shop with person details flattened."""
    sb = get_supabase()
    rows = (
        sb.table("barbers")
        .select("id, person_id, specialty, persons(full_name, phone)")
        .eq("shop_id", shop_id)
        .eq("is_available", True)
        .execute()
        .data or []
    )
    result = []
    for r in rows:
        p = r.get("persons") or {}
        result.append({
            "barber_id": r["id"],
            "person_id": r["person_id"],
            "specialty": r.get("specialty") or "",
            "full_name": p.get("full_name", "—"),
            "phone": p.get("phone", ""),
        })
    return result


def get_barber_by_person(person_id: str) -> dict | None:
    sb = get_supabase()
    res = sb.table("barbers").select("*").eq("person_id", person_id).execute()
    return res.data[0] if res.data else None


def register_barber(person_id: str, shop_id: str, specialty: str | None = None) -> dict:
    sb = get_supabase()
    existing = sb.table("barbers").select("*").eq("person_id", person_id).execute()
    if existing.data:
        return existing.data[0]
    res = sb.table("barbers").insert({
        "person_id": person_id,
        "shop_id": shop_id,
        "specialty": specialty or "",
        "is_available": True,
    }).execute()
    return res.data[0]


# ── Services ───────────────────────────────────────────────────────────────────

def list_services(barber_id: str, only_active: bool = True) -> list[dict]:
    """barber_id is barbers.id (not persons.id)."""
    sb = get_supabase()
    q = sb.table("services").select("*").eq("barber_id", barber_id)
    if only_active:
        q = q.eq("is_active", True)
    return q.order("name").execute().data or []


def create_service(barber_id: str, name: str, duration_minutes: int, price: float) -> dict:
    sb = get_supabase()
    res = sb.table("services").insert({
        "barber_id": barber_id,
        "name": name,
        "duration_minutes": duration_minutes,
        "price": price,
        "is_active": True,
    }).execute()
    return res.data[0]


def delete_service(service_id: str) -> None:
    get_supabase().table("services").update({"is_active": False}).eq("id", service_id).execute()


# ── Appointments ───────────────────────────────────────────────────────────────

_SLOT_STEP = timedelta(minutes=30)
_WORK_START = time(9, 0)
_WORK_END = time(18, 0)


def available_slots(barber_person_id: str, for_date: date, duration_min: int) -> list[time]:
    """Returns available start times (naive, local) for the given barber and date."""
    sb = get_supabase()
    day_start = datetime.combine(for_date, time(0, 0)).isoformat()
    day_end = datetime.combine(for_date, time(23, 59, 59)).isoformat()

    rows = (
        sb.table("appointments")
        .select("scheduled_start, scheduled_end")
        .eq("barber_person_id", barber_person_id)
        .not_.in_("status", ["cancelled"])
        .gte("scheduled_start", day_start)
        .lte("scheduled_start", day_end)
        .execute()
        .data or []
    )

    booked: list[tuple[datetime, datetime]] = [
        (_naive(r["scheduled_start"]), _naive(r["scheduled_end"]))
        for r in rows
    ]

    duration = timedelta(minutes=duration_min)
    slots: list[time] = []
    cursor = datetime.combine(for_date, _WORK_START)
    work_end = datetime.combine(for_date, _WORK_END)

    now_time = datetime.now().time() if for_date == date.today() else None

    while cursor + duration <= work_end:
        slot_end = cursor + duration
        if not any(s < slot_end and e > cursor for s, e in booked):
            if now_time is None or cursor.time() > now_time:
                slots.append(cursor.time())
        cursor += _SLOT_STEP

    return slots


def create_appointment(
    customer_person_id: str,
    barber_person_id: str,
    shop_id: str,
    service_id: str,
    starts_at: datetime,
    duration_min: int,
    price: float,
    notes: str = "",
) -> dict:
    sb = get_supabase()
    ends_at = starts_at + timedelta(minutes=duration_min)

    conflict = (
        sb.table("appointments")
        .select("id")
        .eq("barber_person_id", barber_person_id)
        .not_.in_("status", ["cancelled"])
        .lt("scheduled_start", ends_at.isoformat())
        .gt("scheduled_end", starts_at.isoformat())
        .execute()
    )
    if conflict.data:
        raise ValueError("Bu saat dilimi zaten dolu.")

    res = sb.table("appointments").insert({
        "shop_id": shop_id,
        "customer_person_id": customer_person_id,
        "barber_person_id": barber_person_id,
        "service_id": service_id,
        "scheduled_start": starts_at.isoformat(),
        "scheduled_end": ends_at.isoformat(),
        "total_price": price,
        "status": "pending",
        "customer_notes": notes or None,
    }).execute()

    if not res.data:
        raise ValueError("Randevu oluşturulamadı.")
    return res.data[0]


def list_my_appointments(person_id: str, role: str) -> list[dict]:
    sb = get_supabase()
    if role == "customer":
        return (
            sb.table("appointments")
            .select(
                "id, scheduled_start, scheduled_end, status, total_price, customer_notes, "
                "services(name, duration_minutes, price), "
                "shops(display_name), "
                "barber:persons!appointments_barber_person_id_fkey(full_name, phone)"
            )
            .eq("customer_person_id", person_id)
            .order("scheduled_start", desc=True)
            .execute()
            .data or []
        )
    else:  # barber
        return (
            sb.table("appointments")
            .select(
                "id, scheduled_start, scheduled_end, status, total_price, customer_notes, "
                "customer_person_id, "
                "services(name, duration_minutes, price), "
                "shops(display_name), "
                "customer:persons!appointments_customer_person_id_fkey(full_name, phone)"
            )
            .eq("barber_person_id", person_id)
            .order("scheduled_start")
            .execute()
            .data or []
        )


def update_appointment_status(
    appointment_id: str,
    status: str,
    cancelled_by: str | None = None,
) -> None:
    sb = get_supabase()
    data: dict[str, Any] = {"status": status}
    if status == "cancelled":
        data["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        data["cancelled_by"] = cancelled_by or "barber"
    sb.table("appointments").update(data).eq("id", appointment_id).execute()


# ── Reputation ─────────────────────────────────────────────────────────────────

_TIERS: list[tuple[int, str]] = [
    (85, "Güvenilir"),
    (60, "Normal"),
    (30, "Riskli"),
    (0,  "Kara liste"),
]


def reputation_for(customer_person_id: str) -> dict:
    """Compute reputation score and tier from appointment history."""
    sb = get_supabase()
    rows = (
        sb.table("appointments")
        .select("status, cancelled_by, cancelled_at, scheduled_start")
        .eq("customer_person_id", customer_person_id)
        .execute()
        .data or []
    )

    completed = no_show = late_cancel = 0
    for r in rows:
        if r["status"] == "completed":
            completed += 1
        elif r["status"] == "no_show":
            no_show += 1
        elif r["status"] == "cancelled" and r.get("cancelled_by") == "customer":
            try:
                ca = datetime.fromisoformat(r["cancelled_at"].replace("Z", "+00:00"))
                ss = datetime.fromisoformat(r["scheduled_start"].replace("Z", "+00:00"))
                if ca > ss - timedelta(hours=2):
                    late_cancel += 1
            except Exception:
                pass

    total = len(rows)
    score = max(0, min(100, 100 + completed * 2 - no_show * 15 - late_cancel * 5))

    if total == 0:
        tier = "Yeni"
    else:
        tier = next((lbl for thr, lbl in _TIERS if score >= thr), "Kara liste")

    return {
        "score": score,
        "tier": tier,
        "total_count": total,
        "completed_count": completed,
        "no_show_count": no_show,
        "late_cancel_count": late_cancel,
    }
