"""Berber paneli — randevu yönetimi, hizmet yönetimi."""
from datetime import datetime, date, timedelta

import streamlit as st

from db import (
    create_service,
    delete_service,
    get_barber_by_person,
    get_or_create_shop_for_owner,
    list_my_appointments,
    list_services,
    register_barber,
    reputation_for,
    update_appointment_status,
)

# ── Auth ───────────────────────────────────────────────────────────────────────
user = st.session_state.get("user")
if not user:
    st.warning("Önce giriş yapmalısın.")
    st.page_link("app.py", label="Giriş sayfasına dön")
    st.stop()

if user["role"] != "barber":
    st.info("Bu sayfa yalnızca berber hesapları içindir.")
    st.stop()

# ── İlk kurulum ────────────────────────────────────────────────────────────────
barber = get_barber_by_person(user["id"])
if not barber:
    st.subheader("Hoş geldin! Dükkanını tanıt")
    with st.form("setup_shop"):
        shop_name = st.text_input(
            "Dükkan adı", value=f"{user['full_name'].split()[0]}'in Berber Salonu"
        )
        specialty = st.text_input("Uzmanlık alanın (opsiyonel)", placeholder="Saç & Sakal")
        if st.form_submit_button("Kurulumu Tamamla", type="primary"):
            shop = get_or_create_shop_for_owner(user["id"], shop_name)
            register_barber(user["id"], shop["id"], specialty or None)
            st.success("Dükkan ve berber profilin oluşturuldu!")
            st.rerun()
    st.stop()

# ── Başlık ve istatistikler ────────────────────────────────────────────────────
st.title("Berber Paneli")

all_appts = list_my_appointments(user["id"], "barber")

today_str = date.today().isoformat()
week_end  = (date.today() + timedelta(days=7)).isoformat()

today_appts   = [a for a in all_appts if a["scheduled_start"][:10] == today_str]
pending_appts = [a for a in all_appts if a["status"] == "pending"]
week_appts    = [
    a for a in all_appts
    if today_str <= a["scheduled_start"][:10] <= week_end
    and a["status"] not in ("cancelled",)
]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Bugün", len(today_appts))
c2.metric("Onay Bekleyen", len(pending_appts))
c3.metric("Bu Hafta", len(week_appts))
c4.metric("Toplam", len([a for a in all_appts if a["status"] not in ("cancelled",)]))

st.divider()

# ── Sekmeler ───────────────────────────────────────────────────────────────────
tab_appts, tab_services = st.tabs(["Randevular", "Hizmetlerim"])

# ── TAB 1: Randevular ──────────────────────────────────────────────────────────
STATUS_GROUPS = [
    ("pending",   "Onay Bekleyen"),
    ("confirmed", "Onaylı"),
    ("completed", "Tamamlandı"),
    ("no_show",   "Gelmedi"),
    ("cancelled", "İptal"),
]

with tab_appts:
    if not all_appts:
        st.caption("Henüz gelen randevu yok.")
    else:
        groups: dict[str, list] = {k: [] for k, _ in STATUS_GROUPS}
        for a in all_appts:
            groups.setdefault(a["status"], []).append(a)

        for status_key, label in STATUS_GROUPS:
            items = groups.get(status_key, [])
            if not items:
                continue

            st.subheader(f"{label} ({len(items)})")
            for a in items:
                svc      = (a.get("services") or {}).get("name", "—")
                duration = (a.get("services") or {}).get("duration_minutes", "?")
                cust     = a.get("customer") or {}
                cname    = cust.get("full_name", "—")
                cphone   = cust.get("phone") or "—"
                when     = datetime.fromisoformat(a["scheduled_start"].replace("Z", "+00:00"))
                price    = a.get("total_price")

                rep  = reputation_for(a["customer_person_id"])
                tier = rep["tier"]

                with st.container(border=True):
                    col_info, col_cust, col_act = st.columns([3, 3, 2])

                    col_info.markdown(
                        f"**{when.strftime('%d.%m.%Y %H:%M')}**  \n"
                        f"{svc} · {duration} dk"
                        + (f"  \n{float(price):.0f} TL" if price else "")
                    )
                    col_cust.markdown(
                        f"**{cname}**  \n"
                        f"Tel: {cphone}  \n"
                        f"Skor: {tier} ({rep['score']}/100)"
                    )

                    with col_act:
                        if status_key == "pending":
                            b1, b2 = st.columns(2)
                            if b1.button("Onayla", key=f"ok_{a['id']}", type="primary"):
                                update_appointment_status(a["id"], "confirmed")
                                st.rerun()
                            if b2.button("Reddet", key=f"rej_{a['id']}"):
                                update_appointment_status(a["id"], "cancelled", cancelled_by="barber")
                                st.rerun()
                        elif status_key == "confirmed":
                            b1, b2 = st.columns(2)
                            if b1.button("Tamamlandı", key=f"done_{a['id']}", type="primary"):
                                update_appointment_status(a["id"], "completed")
                                st.rerun()
                            if b2.button("Gelmedi", key=f"ns_{a['id']}"):
                                update_appointment_status(a["id"], "no_show")
                                st.rerun()

# ── TAB 2: Hizmetlerim ─────────────────────────────────────────────────────────
with tab_services:
    services = list_services(barber["id"], only_active=False)

    st.subheader("Mevcut Hizmetler")
    if not services:
        st.caption("Henüz hizmet eklemedin.")
    else:
        for s in services:
            active_label = "Aktif" if s["is_active"] else "Pasif"
            with st.container(border=True):
                sc1, sc2 = st.columns([5, 1])
                sc1.markdown(
                    f"**{s['name']}** · {s['duration_minutes']} dk · "
                    f"{float(s['price']):.0f} TL · {active_label}"
                )
                if s["is_active"]:
                    if sc2.button("Kaldır", key=f"del_svc_{s['id']}", use_container_width=True):
                        delete_service(s["id"])
                        st.rerun()

    st.divider()
    st.subheader("Yeni Hizmet Ekle")
    with st.form("svc_form", clear_on_submit=True):
        name = st.text_input("Hizmet adı", placeholder="Saç Kesimi")
        fc1, fc2 = st.columns(2)
        duration = fc1.number_input("Süre (dk)", min_value=5, max_value=240, value=30, step=5)
        price    = fc2.number_input("Ücret (TL)", min_value=0.0, value=250.0, step=10.0)
        if st.form_submit_button("Ekle", type="primary"):
            if not name.strip():
                st.error("Hizmet adı boş olamaz.")
            else:
                try:
                    create_service(barber["id"], name.strip(), int(duration), float(price))
                    st.success(f"'{name}' hizmeti eklendi.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Hata: {e}")
