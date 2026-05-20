"""
BarberSync — Screen 3: Barber Daily Schedule
Shows today's appointments; barber can update status and submit reviews.
"""
import streamlit as st
from datetime import date, timedelta
from modules.appointments import (
    get_barber_appointments,
    update_appointment_status,
    submit_review,
)

# ── auth guard ────────────────────────────────────────────────────────────────
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("Bu sayfayı görüntülemek için giriş yapmanız gerekiyor.")
    st.stop()

user = st.session_state.user
if user["primary_role"] != "barber":
    st.warning("Bu sayfa yalnızca berberler içindir.")
    st.stop()

# ── date picker ───────────────────────────────────────────────────────────────
st.title("Günlük Program")

selected_date = st.date_input(
    "Tarih Seç",
    value=date.today(),
    min_value=date.today() - timedelta(days=30),
    max_value=date.today() + timedelta(days=30),
)

st.divider()

# ── load appointments ─────────────────────────────────────────────────────────
try:
    appts = get_barber_appointments(user["id"], selected_date)
except Exception as e:
    st.error(f"Randevular yüklenemedi: {e}")
    appts = []

if not appts:
    st.info("Seçilen tarihte randevunuz bulunmuyor.")
else:
    st.subheader(f"{selected_date.strftime('%d.%m.%Y')} — {len(appts)} Randevu")

    status_tr = {
        "confirmed":           "Onaylandı",
        "completed":           "Tamamlandı",
        "no_show":             "Gelmedi",
        "cancelled_by_customer": "İptal (Müşteri)",
        "cancelled_by_shop":   "İptal (İşletme)",
        "pending":             "Bekliyor",
        "late_cancel":         "Geç İptal",
    }

    TERMINAL = {"completed", "no_show", "cancelled_by_customer", "cancelled_by_shop", "late_cancel"}

    for appt in appts:
        customer_name = (appt.get("persons") or {}).get("full_name", "—")
        svc_name      = (appt.get("services") or {}).get("name", "—")
        start_str     = appt["scheduled_start"][:16].replace("T", " ")
        status        = appt["status"]
        status_label  = status_tr.get(status, status)
        price         = float(appt.get("total_price_snapshot", 0))

        with st.expander(f"🕐 {start_str}  |  {customer_name}  |  {svc_name}  |  {status_label}"):
            col_info, col_actions = st.columns([2, 1])

            with col_info:
                st.write(f"**Müşteri:** {customer_name}")
                st.write(f"**Hizmet:** {svc_name}")
                st.write(f"**Ücret:** {price:.2f} TL")
                st.write(f"**Durum:** {status_label}")
                if appt.get("customer_notes"):
                    st.info(f"Müşteri Notu: {appt['customer_notes']}")

            with col_actions:
                if status not in TERMINAL:
                    st.markdown("**Durum Güncelle**")
                    new_status = st.selectbox(
                        "Yeni Durum",
                        ["completed", "no_show", "cancelled_by_shop"],
                        format_func=lambda x: status_tr.get(x, x),
                        key=f"status_sel_{appt['id']}",
                    )
                    reason = st.text_input("Neden (isteğe bağlı)", key=f"reason_{appt['id']}")
                    if st.button("Güncelle", key=f"upd_{appt['id']}", type="primary"):
                        try:
                            update_appointment_status(
                                appt["id"], new_status, user["id"], reason or None
                            )
                            st.success("Durum güncellendi.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
                else:
                    st.success(f"Sonuçlandı: {status_label}")

            # review submission for completed appointments without a review
            if status == "completed":
                existing_review = appt.get("review_submitted", False)
                if not existing_review:
                    st.markdown("---")
                    st.markdown("**Müşteriyi Değerlendir**")
                    rating  = st.slider("Puan", 1, 5, 5, key=f"rating_{appt['id']}")
                    comment = st.text_area("Yorum (isteğe bağlı)", key=f"comment_{appt['id']}")
                    if st.button("Değerlendirme Gönder", key=f"rev_{appt['id']}"):
                        try:
                            submit_review(
                                appointment_id    = appt["id"],
                                shop_id           = appt["shop_id"],
                                barber_person_id  = user["id"],
                                reviewer_person_id= user["id"],
                                rating            = rating,
                                comment           = comment or None,
                            )
                            st.success("Değerlendirme kaydedildi.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

# ── quick stats strip ─────────────────────────────────────────────────────────
if appts:
    st.divider()
    total     = len(appts)
    completed = sum(1 for a in appts if a["status"] == "completed")
    no_shows  = sum(1 for a in appts if a["status"] == "no_show")
    revenue   = sum(float(a.get("total_price_snapshot", 0)) for a in appts if a["status"] == "completed")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam",      total)
    c2.metric("Tamamlandı",  completed)
    c3.metric("Gelmedi",     no_shows)
    c4.metric("Günlük Ciro", f"{revenue:.2f} TL")
