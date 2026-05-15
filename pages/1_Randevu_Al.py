"""Müşteri — Randevu alma ve yönetim sayfası."""
from datetime import date, datetime, timedelta

import streamlit as st

from db import (
    available_slots,
    create_appointment,
    list_barbers,
    list_my_appointments,
    list_services,
    list_shops,
    reputation_for,
    update_appointment_status,
)

# ── Auth ───────────────────────────────────────────────────────────────────────
user = st.session_state.get("user")
if not user:
    st.warning("Önce giriş yapmalısın.")
    st.page_link("app.py", label="Giriş sayfasına dön")
    st.stop()

if user["role"] != "customer":
    st.info("Bu sayfa yalnızca müşteri hesapları içindir.")
    st.stop()

# ── İtibar rozeti ──────────────────────────────────────────────────────────────
rep = reputation_for(user["id"])
st.markdown(
    f"**{user['full_name']}** &nbsp;|&nbsp; "
    f"İtibar Skoru: **{rep['score']}/100** — _{rep['tier']}_"
)
st.divider()

# ── Yeni Randevu Formu ─────────────────────────────────────────────────────────
st.subheader("Yeni Randevu")

shops = list_shops()
if not shops:
    st.warning("Sistemde kayıtlı aktif dükkan bulunamadı.")
    st.stop()

shop_id = st.selectbox(
    "Dükkan seç",
    options=[s["id"] for s in shops],
    format_func=lambda i: next(s["display_name"] for s in shops if s["id"] == i),
)

barbers = list_barbers(shop_id)
if not barbers:
    st.warning("Bu dükkanda müsait berber yok.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    barber_id = st.selectbox(
        "Berber seç",
        options=[b["barber_id"] for b in barbers],
        format_func=lambda i: next(
            f"{b['full_name']}{' — ' + b['specialty'] if b['specialty'] else ''}"
            for b in barbers if b["barber_id"] == i
        ),
    )
selected_barber = next(b for b in barbers if b["barber_id"] == barber_id)

services = list_services(barber_id)
if not services:
    st.warning("Bu berberin henüz tanımlı hizmeti yok.")
    st.stop()

with col2:
    service_id = st.selectbox(
        "Hizmet seç",
        options=[s["id"] for s in services],
        format_func=lambda i: next(
            f"{s['name']} · {s['duration_minutes']} dk · {s['price']} TL"
            for s in services if s["id"] == i
        ),
    )
selected_service = next(s for s in services if s["id"] == service_id)

today = date.today()
appt_date = st.date_input(
    "Tarih",
    value=today,
    min_value=today,
    max_value=today + timedelta(days=30),
)

slots = available_slots(selected_barber["person_id"], appt_date, selected_service["duration_minutes"])

if not slots:
    st.error("Bu gün için uygun saat yok. Başka bir gün deneyin.")
    st.stop()

chosen_slot = st.select_slider(
    "Saat seç",
    options=[t.strftime("%H:%M") for t in slots],
)
slot_map = {t.strftime("%H:%M"): t for t in slots}

notes = st.text_area("Not (opsiyonel)", placeholder="Sakal şekli, saç boyu vb.", max_chars=300)

if st.button("Randevuyu Onayla", type="primary", use_container_width=True):
    try:
        starts_at = datetime.combine(appt_date, slot_map[chosen_slot])
        create_appointment(
            customer_person_id=user["id"],
            barber_person_id=selected_barber["person_id"],
            shop_id=shop_id,
            service_id=service_id,
            starts_at=starts_at,
            duration_min=selected_service["duration_minutes"],
            price=float(selected_service["price"]),
            notes=notes,
        )
        st.success(
            f"Randevu oluşturuldu! {appt_date.strftime('%d.%m.%Y')} {chosen_slot} — "
            f"**{selected_barber['full_name']}** · **{selected_service['name']}**"
        )
        st.balloons()
        st.rerun()
    except ValueError as ve:
        st.error(str(ve))
    except Exception as e:
        st.error(f"Beklenmedik hata: {e}")

# ── Randevularım ───────────────────────────────────────────────────────────────
st.divider()
st.subheader("Randevularım")

all_appts = list_my_appointments(user["id"], "customer")
if not all_appts:
    st.caption("Henüz randevun yok.")
    st.stop()

STATUS_LABEL = {
    "pending":   "Onay Bekleniyor",
    "confirmed": "Onaylı",
    "completed": "Tamamlandı",
    "cancelled": "İptal Edildi",
    "no_show":   "Gelmedi",
}

active = [a for a in all_appts if a["status"] in ("pending", "confirmed")]
past   = [a for a in all_appts if a["status"] not in ("pending", "confirmed")]

tab_active, tab_past = st.tabs([f"Aktif ({len(active)})", f"Geçmiş ({len(past)})"])


def _render_appt(a: dict, show_cancel: bool = False) -> None:
    svc       = (a.get("services") or {}).get("name", "—")
    duration  = (a.get("services") or {}).get("duration_minutes", "?")
    price     = (a.get("services") or {}).get("price")
    barber    = (a.get("barber") or {}).get("full_name", "—")
    shop      = (a.get("shops") or {}).get("display_name", "")
    when      = datetime.fromisoformat(a["scheduled_start"].replace("Z", "+00:00"))
    status_tr = STATUS_LABEL.get(a["status"], a["status"])

    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        c1.markdown(
            f"**{when.strftime('%d.%m.%Y %H:%M')}**  \n"
            f"{svc} · {duration} dk"
            + (f" · {float(price):.0f} TL" if price else "")
            + f"  \nBerber: {barber}"
            + (f" · {shop}" if shop else "")
            + f"  \n_{status_tr}_"
        )
        if show_cancel and a["status"] in ("pending", "confirmed"):
            if c2.button("İptal", key=f"cancel_{a['id']}", use_container_width=True):
                update_appointment_status(a["id"], "cancelled", cancelled_by="customer")
                st.rerun()


with tab_active:
    if not active:
        st.caption("Aktif randevun yok.")
    for a in active:
        _render_appt(a, show_cancel=True)

with tab_past:
    if not past:
        st.caption("Geçmiş randevu yok.")
    for a in past:
        _render_appt(a, show_cancel=False)
