"""Reporting & Analytics — KPIs, staff performance snapshots, revenue dashboards."""
from __future__ import annotations
from datetime import datetime, timezone, date, timedelta
from db.connection import get_client


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- shop KPIs (owner dashboard) --------------------------------------

def get_shop_kpis(shop_id: str) -> dict:
    sb = get_client()
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    today_end   = today_start + timedelta(days=1)

    appts = (
        sb.table("appointments")
        .select("id, status, total_price_snapshot")
        .eq("shop_id", shop_id)
        .gte("scheduled_start", today_start.isoformat())
        .lt("scheduled_start",  today_end.isoformat())
        .execute()
        .data
    )

    total       = len(appts)
    completed   = sum(1 for a in appts if a["status"] == "completed")
    no_shows    = sum(1 for a in appts if a["status"] == "no_show")
    revenue_today = sum(
        float(a["total_price_snapshot"])
        for a in appts if a["status"] == "completed"
    )
    no_show_rate = round(no_shows / total * 100, 1) if total else 0.0

    # low stock count
    from modules.inventory import get_low_stock
    low_stock_count = len(get_low_stock(shop_id))

    return {
        "total_today":    total,
        "completed_today": completed,
        "no_show_rate":   no_show_rate,
        "revenue_today":  revenue_today,
        "low_stock_count": low_stock_count,
    }


def get_recent_appointments(shop_id: str, limit: int = 10) -> list[dict]:
    sb = get_client()
    return (
        sb.table("appointments")
        .select(
            "id, status, scheduled_start, total_price_snapshot,"
            "persons!customer_person_id(full_name),"
            "persons!barber_person_id(full_name)"
        )
        .eq("shop_id", shop_id)
        .order("scheduled_start", desc=True)
        .limit(limit)
        .execute()
        .data
    )


# ---------- staff performance ------------------------------------------------

def refresh_performance_snapshot(
    shop_id: str,
    barber_person_id: str,
    year: int,
    month: int,
) -> dict:
    """Recompute and upsert the monthly snapshot for a barber."""
    sb = get_client()
    month_start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        month_end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    appts = (
        sb.table("appointments")
        .select("id, status, total_price_snapshot")
        .eq("shop_id", shop_id)
        .eq("barber_person_id", barber_person_id)
        .gte("scheduled_start", month_start.isoformat())
        .lt("scheduled_start",  month_end.isoformat())
        .execute()
        .data
    )

    scheduled  = len(appts)
    completed  = sum(1 for a in appts if a["status"] == "completed")
    no_shows   = sum(1 for a in appts if a["status"] == "no_show")
    cancelled  = sum(1 for a in appts if a["status"] in ("cancelled_by_customer", "cancelled_by_shop"))
    revenue    = sum(float(a["total_price_snapshot"]) for a in appts if a["status"] == "completed")
    no_show_rate     = round(no_shows   / scheduled, 4) if scheduled else 0.0
    cancellation_rate = round(cancelled / scheduled, 4) if scheduled else 0.0

    appt_ids = [a["id"] for a in appts]
    avg_rating = None
    if appt_ids:
        reviews = (
            sb.table("reviews")
            .select("rating")
            .in_("appointment_id", appt_ids)
            .execute()
            .data
        )
        if reviews:
            avg_rating = round(sum(r["rating"] for r in reviews) / len(reviews), 2)

    is_bonus = completed >= 30 and no_show_rate <= 0.05 and (avg_rating or 0) >= 4.0

    snapshot = {
        "shop_id":                shop_id,
        "barber_person_id":       barber_person_id,
        "period_year":            year,
        "period_month":           month,
        "appointments_completed": completed,
        "appointments_scheduled": scheduled,
        "total_revenue":          revenue,
        "no_show_rate":           no_show_rate,
        "cancellation_rate":      cancellation_rate,
        "average_rating":         avg_rating,
        "is_bonus_eligible":      is_bonus,
        "generated_at":           _now(),
        "updated_at":             _now(),
    }

    existing = (
        sb.table("barber_performance_snapshots")
        .select("id")
        .eq("shop_id", shop_id)
        .eq("barber_person_id", barber_person_id)
        .eq("period_year", year)
        .eq("period_month", month)
        .execute()
        .data
    )
    if existing:
        sb.table("barber_performance_snapshots").update(snapshot).eq("id", existing[0]["id"]).execute()
    else:
        snapshot["created_at"] = _now()
        sb.table("barber_performance_snapshots").insert(snapshot).execute()

    return snapshot


def get_staff_performance(shop_id: str, year: int, month: int) -> list[dict]:
    """Return performance snapshots for all barbers, refreshing if missing."""
    sb = get_client()

    barbers = (
        sb.table("barber_profiles")
        .select("person_id, display_name")
        .eq("shop_id", shop_id)
        .eq("is_active", True)
        .execute()
        .data
    )

    result = []
    for b in barbers:
        snaps = (
            sb.table("barber_performance_snapshots")
            .select("*")
            .eq("shop_id", shop_id)
            .eq("barber_person_id", b["person_id"])
            .eq("period_year", year)
            .eq("period_month", month)
            .execute()
            .data
        )
        if snaps:
            snap = snaps[0]
        else:
            snap = refresh_performance_snapshot(shop_id, b["person_id"], year, month)

        snap["barber_name"] = b["display_name"] or b["person_id"]
        result.append(snap)

    return result


def get_revenue_trend(shop_id: str, days: int = 30) -> list[dict]:
    """Return daily revenue for the last N days."""
    sb = get_client()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    appts = (
        sb.table("appointments")
        .select("scheduled_start, total_price_snapshot, status")
        .eq("shop_id", shop_id)
        .eq("status", "completed")
        .gte("scheduled_start", since)
        .execute()
        .data
    )

    daily: dict[str, float] = {}
    for a in appts:
        day = a["scheduled_start"][:10]
        daily[day] = daily.get(day, 0.0) + float(a["total_price_snapshot"])

    return [{"date": d, "revenue": v} for d, v in sorted(daily.items())]
