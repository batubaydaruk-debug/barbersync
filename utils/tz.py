"""Timezone helpers — Turkey is permanently UTC+3 since 2016."""
from datetime import datetime, timezone, timedelta

TZ_TR = timezone(timedelta(hours=3))


def utc_str_to_tr(iso_str: str) -> datetime:
    """Parse a UTC ISO string and return Turkey-local datetime."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_TR)


def fmt_tr(iso_str: str, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Format a UTC ISO string as Turkey local time string."""
    return utc_str_to_tr(iso_str).strftime(fmt)


def today_tr_range():
    """Return (start, end) as UTC-aware datetimes covering today in Turkey time."""
    now_tr = datetime.now(TZ_TR)
    start  = now_tr.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    end    = start + timedelta(days=1)
    return start, end
