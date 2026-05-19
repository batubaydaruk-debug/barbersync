"""User Management module — registration, login, KVKK consent."""
from __future__ import annotations
import bcrypt
from datetime import datetime, timezone
from db.connection import get_client


# ---------- helpers ----------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _get_active_privacy_version() -> str | None:
    sb = get_client()
    res = sb.table("privacy_notice_versions").select("id").eq("is_active", True).limit(1).execute()
    return res.data[0]["id"] if res.data else None


# ---------- public API -------------------------------------------------------

def register_user(
    full_name: str,
    email: str,
    phone: str,
    password: str,
    role: str,
    accepted_privacy: bool,
) -> dict:
    """Create a new person record + role assignment + profile. Returns person dict."""
    if not accepted_privacy:
        raise ValueError("KVKK Gizlilik Bildirimi kabul edilmelidir.")
    if len(password) < 6:
        raise ValueError("Şifre en az 6 karakter olmalıdır.")

    sb = get_client()

    # uniqueness checks
    if sb.table("persons").select("id").eq("email", email).execute().data:
        raise ValueError("Bu e-posta adresi zaten kayıtlı.")
    if sb.table("persons").select("id").eq("phone", phone).execute().data:
        raise ValueError("Bu telefon numarası zaten kayıtlı.")

    person = sb.table("persons").insert({
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "password_hash": _hash_password(password),
        "has_accepted_privacy_notice": True,
        "created_at": _now(),
        "updated_at": _now(),
    }).execute().data[0]

    person_id = person["id"]

    # role
    role_row = sb.table("roles").select("id").eq("role_name", role).execute().data
    if not role_row:
        raise ValueError(f"Geçersiz rol: {role}")
    sb.table("person_roles").insert({
        "person_id": person_id,
        "role_id": role_row[0]["id"],
        "is_active": True,
    }).execute()

    # profile
    if role == "customer":
        sb.table("customer_profiles").insert({
            "person_id": person_id,
            "reputation_score": 100,
            "total_appointments_count": 0,
            "total_no_shows_count": 0,
        }).execute()

    # KVKK consent log
    pv_id = _get_active_privacy_version()
    if pv_id:
        sb.table("consent_logs").insert({
            "person_id": person_id,
            "consent_type": "privacy_notice",
            "privacy_notice_version_id": pv_id,
            "granted_at": _now(),
        }).execute()

    return person


def login_user(email: str, password: str) -> dict:
    """Verify credentials and return user dict with roles and shop_id."""
    sb = get_client()

    rows = (
        sb.table("persons")
        .select("*")
        .eq("email", email)
        .is_("deleted_at", "null")
        .execute()
        .data
    )
    if not rows:
        raise ValueError("E-posta veya şifre hatalı.")
    person = rows[0]

    if not _verify_password(password, person["password_hash"]):
        raise ValueError("E-posta veya şifre hatalı.")

    # roles
    role_rows = (
        sb.table("person_roles")
        .select("roles(role_name), shop_id")
        .eq("person_id", person["id"])
        .eq("is_active", True)
        .execute()
        .data
    )
    user_roles = [r["roles"]["role_name"] for r in role_rows if r.get("roles")]
    shop_ids   = [r["shop_id"] for r in role_rows if r.get("shop_id")]

    sb.table("persons").update({"last_login_at": _now()}).eq("id", person["id"]).execute()

    return {
        "id":           person["id"],
        "full_name":    person["full_name"],
        "email":        person["email"],
        "phone":        person["phone"],
        "roles":        user_roles,
        "primary_role": user_roles[0] if user_roles else "customer",
        "shop_id":      shop_ids[0] if shop_ids else None,
    }


def create_shop_for_owner(
    owner_person_id: str,
    display_name: str,
    legal_name: str,
    city: str = "",
    address_line1: str = "",
) -> dict:
    """Create a shop and assign the owner to it."""
    sb = get_client()
    shop = sb.table("shops").insert({
        "owner_person_id": owner_person_id,
        "display_name":    display_name,
        "legal_name":      legal_name or display_name,
        "city":            city,
        "address_line1":   address_line1,
        "is_active":       True,
        "is_accepting_appointments": True,
        "created_at": _now(),
        "updated_at": _now(),
    }).execute().data[0]

    shop_id = shop["id"]

    # bind owner role to this shop
    role_row = sb.table("roles").select("id").eq("role_name", "owner").execute().data
    if role_row:
        sb.table("person_roles").update({"shop_id": shop_id}).eq(
            "person_id", owner_person_id
        ).execute()

    return shop


def get_shop_for_owner(owner_person_id: str) -> dict | None:
    sb = get_client()
    rows = (
        sb.table("shops")
        .select("*")
        .eq("owner_person_id", owner_person_id)
        .eq("is_active", True)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def register_barber_to_shop(barber_person_id: str, shop_id: str) -> dict:
    """Create a barber_profile and link the person_role to the shop."""
    sb = get_client()

    # check not already in this shop
    existing = (
        sb.table("barber_profiles")
        .select("id")
        .eq("person_id", barber_person_id)
        .eq("shop_id", shop_id)
        .execute()
        .data
    )
    if existing:
        return existing[0]

    person = sb.table("persons").select("full_name").eq("id", barber_person_id).execute().data[0]
    profile = sb.table("barber_profiles").insert({
        "person_id":    barber_person_id,
        "shop_id":      shop_id,
        "display_name": person["full_name"],
        "is_active":    True,
        "is_accepting_appointments": True,
        "created_at": _now(),
        "updated_at": _now(),
    }).execute().data[0]

    # update person_role with shop
    sb.table("person_roles").update({"shop_id": shop_id}).eq(
        "person_id", barber_person_id
    ).execute()

    return profile


def require_role(user: dict | None, *roles: str) -> None:
    """Raise ValueError if user is None or doesn't have one of the required roles."""
    if user is None:
        raise PermissionError("Giriş yapmanız gerekiyor.")
    if roles and user.get("primary_role") not in roles:
        raise PermissionError("Bu sayfaya erişim yetkiniz yok.")
