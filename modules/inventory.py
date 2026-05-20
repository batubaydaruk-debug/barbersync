"""Inventory Management — stock tracking, threshold alerts, shortage drafts."""
from __future__ import annotations
from datetime import datetime, timezone
from db.connection import get_client


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- products ---------------------------------------------------------

def list_products(shop_id: str) -> list[dict]:
    sb = get_client()
    return (
        sb.table("products")
        .select(
            "id, sku, name, unit_of_measure, current_stock, min_threshold, "
            "reorder_quantity, unit_cost, is_active, "
            "product_categories(name), suppliers(name)"
        )
        .eq("shop_id", shop_id)
        .eq("is_active", True)
        .is_("deleted_at", "null")
        .order("name")
        .execute()
        .data
    )


def list_low_stock_products(shop_id: str) -> list[dict]:
    sb = get_client()
    return (
        sb.table("products")
        .select(
            "id, name, sku, unit_of_measure, current_stock, min_threshold, "
            "reorder_quantity, preferred_supplier_id, suppliers(name, contact_email)"
        )
        .eq("shop_id", shop_id)
        .eq("is_active", True)
        .is_("deleted_at", "null")
        .lt("current_stock", sb.table("products").select("min_threshold"))   # handled via filter below
        .execute()
        .data
    )


def get_low_stock(shop_id: str) -> list[dict]:
    """Return products whose current_stock < min_threshold."""
    products = list_products(shop_id)
    return [p for p in products if float(p["current_stock"]) < float(p["min_threshold"])]


def add_product(
    shop_id: str,
    name: str,
    sku: str | None = None,
    category_id: str | None = None,
    unit_of_measure: str = "adet",
    initial_stock: float = 0.0,
    min_threshold: float = 5.0,
    reorder_quantity: float = 10.0,
    unit_cost: float | None = None,
    supplier_id: str | None = None,
) -> dict:
    sb = get_client()
    return sb.table("products").insert({
        "shop_id":              shop_id,
        "product_category_id":  category_id,
        "preferred_supplier_id": supplier_id,
        "sku":                  sku,
        "name":                 name,
        "unit_of_measure":      unit_of_measure,
        "min_threshold":        min_threshold,
        "reorder_quantity":     reorder_quantity,
        "unit_cost":            unit_cost,
        "current_stock":        initial_stock,
        "is_active":            True,
        "created_at":           _now(),
        "updated_at":           _now(),
    }).execute().data[0]


def update_stock(
    shop_id: str,
    product_id: str,
    quantity_delta: float,
    movement_type: str,
    performed_by: str | None = None,
    notes: str = "",
) -> float:
    """Apply a stock movement and return the updated stock level."""
    sb = get_client()

    sb.table("stock_movements").insert({
        "shop_id":              shop_id,
        "product_id":           product_id,
        "movement_type":        movement_type,
        "quantity_delta":       quantity_delta,
        "performed_by_person_id": performed_by,
        "notes":                notes,
        "performed_at":         _now(),
    }).execute()

    product = sb.table("products").select("current_stock").eq("id", product_id).execute().data[0]
    new_stock = float(product["current_stock"]) + quantity_delta

    sb.table("products").update({
        "current_stock": new_stock,
        "updated_at":    _now(),
    }).eq("id", product_id).execute()

    return new_stock


# ---------- shortage drafts --------------------------------------------------

def generate_shortage_draft(shop_id: str, generated_by: str | None = None) -> dict:
    """Auto-generate a shortage draft for all below-threshold products."""
    sb   = get_client()
    low  = get_low_stock(shop_id)

    if not low:
        return None

    draft = sb.table("shortage_drafts").insert({
        "shop_id":              shop_id,
        "generated_at":         _now(),
        "generated_by_person_id": generated_by,
        "status":               "draft",
        "created_at":           _now(),
        "updated_at":           _now(),
    }).execute().data[0]

    draft_id = draft["id"]
    items = []
    for p in low:
        recommended = float(p["reorder_quantity"]) or (float(p["min_threshold"]) - float(p["current_stock"]))
        item = sb.table("shortage_draft_items").insert({
            "shortage_draft_id":      draft_id,
            "product_id":             p["id"],
            "current_stock_snapshot": float(p["current_stock"]),
            "min_threshold_snapshot": float(p["min_threshold"]),
            "recommended_quantity":   recommended,
            "preferred_supplier_id":  p.get("preferred_supplier_id"),
            "created_at":             _now(),
            "updated_at":             _now(),
        }).execute().data[0]
        items.append(item)

    draft["items"] = items
    return draft


def list_shortage_drafts(shop_id: str) -> list[dict]:
    sb = get_client()
    return (
        sb.table("shortage_drafts")
        .select("id, status, generated_at, reviewed_at, notes, persons!generated_by_person_id(full_name)")
        .eq("shop_id", shop_id)
        .is_("deleted_at", "null")
        .order("generated_at", desc=True)
        .limit(20)
        .execute()
        .data
    )


def get_draft_with_items(draft_id: str) -> dict | None:
    sb = get_client()
    drafts = (
        sb.table("shortage_drafts")
        .select("*")
        .eq("id", draft_id)
        .execute()
        .data
    )
    if not drafts:
        return None
    draft = drafts[0]
    draft["items"] = (
        sb.table("shortage_draft_items")
        .select(
            "*, products(name, sku, unit_of_measure), "
            "suppliers(name, contact_email, contact_phone)"
        )
        .eq("shortage_draft_id", draft_id)
        .execute()
        .data
    )
    return draft


def update_draft_status(draft_id: str, new_status: str, reviewed_by: str | None = None) -> None:
    sb = get_client()
    payload: dict = {"status": new_status, "updated_at": _now()}
    if new_status == "sent":
        payload["reviewed_at"] = _now()
        payload["reviewed_by_person_id"] = reviewed_by
    sb.table("shortage_drafts").update(payload).eq("id", draft_id).execute()


# ---------- categories & suppliers -------------------------------------------

def list_categories(shop_id: str) -> list[dict]:
    sb = get_client()
    return (
        sb.table("product_categories")
        .select("id, name")
        .eq("shop_id", shop_id)
        .eq("is_active", True)
        .is_("deleted_at", "null")
        .execute()
        .data
    )


def ensure_default_category(shop_id: str) -> dict:
    """Return or create a default 'Genel' category dict."""
    sb  = get_client()
    cats = list_categories(shop_id)
    if cats:
        return cats[0]
    row = sb.table("product_categories").insert({
        "shop_id":   shop_id,
        "name":      "Genel",
        "is_active": True,
        "created_at": _now(),
        "updated_at": _now(),
    }).execute().data[0]
    return {"id": row["id"], "name": "Genel"}


def list_suppliers(shop_id: str) -> list[dict]:
    sb = get_client()
    return (
        sb.table("suppliers")
        .select("id, name, contact_email, contact_phone")
        .eq("shop_id", shop_id)
        .eq("is_active", True)
        .is_("deleted_at", "null")
        .execute()
        .data
    )
