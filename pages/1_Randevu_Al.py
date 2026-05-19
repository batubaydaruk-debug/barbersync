"""
BarberSync — Screen 2: Customer Booking Page
4-step flow: Select Barber → Select Service → Select Date/Time → Upload Photo → Confirm
"""
import streamlit as st
from datetime import date, datetime, timezone, timedelta
from modules.appointments import (
    list_shops, list_barbers, list_services,
    get_available_slots, create_appointment,
    upload_reference_photo, get_customer_appointments,
    check_booking_allowed,
)
from modules.reputation import get_reputation_profile
from utils.gemini import predict_noshow, store_prediction

st.set_page_config(page_title="Randevu Al — BarberSync", page_icon="✂️", layout="wide")

# ── auth guard ────────────────────────────────────────────────────────────────
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("Bu sayfayı görüntülemek için giriş yapmanız gerekiyor.")
    st.page_link("app.py", label="Giriş Yap")
    st.stop()

user = st.session_state.user
if user["primary_role"] != "customer":
    st.warning("Bu sayfa yalnızca müşteriler içindir.")
    st.stop()

# ── sidebar: user info ────────────────────────────────────────────────────────
st.sidebar.markdown(f"**{user['full_name']}**")
st.sidebar.caption("Müşteri")
if st.sidebar.button("Çıkış Yap"):
    st.session_state.user = None
    st.rerun()

# ── reputation banner ─────────────────────────────────────────────────────────
try:
    rep   = get_reputation_profile(user["id"])
    score = rep["reputation_score"]
    tier  = rep["tier"]
    if tier == "Yeşil":
        st.sidebar.success(f"İtibar Puanı: {score}/100")
    elif tier == "Sarı":
        st.sidebar.warning(f"İtibar Puanı: {score}/100")
    else:
        st.sidebar.error(f"İtibar Puanı: {score}/100")
except Exception:
    score = 100

# ── session state for multi-step flow ────────────────────────────────────────
for key, default in [
    ("bk_step", 1), ("bk_shop", None), ("bk_barber", None),
    ("bk_service", None), ("bk_date", None), ("bk_slot", None),
    ("bk_photo", None), ("bk_confirmed", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def reset_booking():
    for k in ["bk_step","bk_shop","bk_barber","bk_service","bk_date","bk_slot","bk_photo","bk_confirmed"]:
        st.session_state[k] = None if k != "bk_step" else 1
    st.session_state["bk_confirmed"] = False


# ── header ────────────────────────────────────────────────────────────────────
st.title("Randevu Al")

# ── step indicator ────────────────────────────────────────────────────────────
steps = ["1. Berber Seç", "2. Hizmet Seç", "3. Tarih & Saat", "4. Fotoğraf & Onayla"]
cols  = st.columns(len(steps))
for i, (c, label) in enumerate(zip(cols, steps), start=1):
    with c:
        if i < st.session_state.bk_step:
            st.success(label)
        elif i == st.session_state.bk_step:
            st.info(f"**{label}**")
        else:
            st.markdown(f":gray[{label}]")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Select Shop & Barber
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.bk_step == 1:
    st.subheader("Berber Seç")
    try:
        shops = list_shops()
    except Exception as e:
        st.error(f"İşletmeler yüklenemedi: {e}")
        st.stop()

    if not shops:
        st.info("Şu an aktif işletme bulunmuyor.")
        st.stop()

    shop_map = {s["display_name"]: s for s in shops}
    chosen_shop_name = st.selectbox("İşletme", list(shop_map.keys()))
    chosen_shop = shop_map[chosen_shop_name]

    try:
        barbers = list_barbers(chosen_shop["id"])
    except Exception as e:
        st.error(f"Berberler yüklenemedi: {e}")
        barbers = []

    if not barbers:
        st.warning("Bu işletmede aktif berber bulunmuyor.")
    else:
        b_cols = st.columns(min(len(barbers), 4))
        selected_barber = None
        for col, b in zip(b_cols, barbers):
            with col:
                st.markdown(f"**{b['display_name'] or 'Berber'}**")
                if st.button("Seç", key=f"sel_barber_{b['id']}"):
                    selected_barber = b

        if selected_barber:
            st.session_state.bk_shop    = chosen_shop
            st.session_state.bk_barber  = selected_barber
            st.session_state.bk_step    = 2
            st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Select Service
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.bk_step == 2:
    st.subheader("Hizmet Seç")
    barber  = st.session_state.bk_barber
    shop    = st.session_state.bk_shop
    st.caption(f"Berber: **{barber['display_name']}**")

    try:
        services = list_services(shop["id"], barber["id"])
    except Exception as e:
        st.error(f"Hizmetler yüklenemedi: {e}")
        services = []

    if not services:
        st.warning("Bu berber için aktif hizmet tanımlı değil.")
    else:
        svc_map = {f"{s['name']}  —  {int(s.get('duration_minutes', s.get('default_duration_minutes',30)))} dk  |  {float(s.get('price', s.get('base_price',0))):.2f} TL": s for s in services}
        chosen_svc_label = st.selectbox("Hizmet", list(svc_map.keys()))
        chosen_svc = svc_map[chosen_svc_label]

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Devam Et", type="primary"):
                st.session_state.bk_service = chosen_svc
                st.session_state.bk_step    = 3
                st.rerun()
        with c2:
            if st.button("Geri"):
                st.session_state.bk_step = 1
                st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Date & Time
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.bk_step == 3:
    st.subheader("Tarih ve Saat Seç")
    svc    = st.session_state.bk_service
    barber = st.session_state.bk_barber
    dur    = int(svc.get("duration_minutes", svc.get("default_duration_minutes", 30)))
    st.caption(f"Hizmet: **{svc['name']}**  |  Süre: {dur} dk")

    chosen_date = st.date_input(
        "Tarih",
        value=date.today() + timedelta(days=1),
        min_value=date.today(),
        max_value=date.today() + timedelta(days=30),
    )

    try:
        slots = get_available_slots(barber["person_id"], chosen_date, dur)
    except Exception as e:
        st.error(f"Müsait saatler yüklenemedi: {e}")
        slots = []

    if not slots:
        st.warning("Seçilen tarihte müsait saat bulunamadı. Lütfen başka bir gün seçin.")
    else:
        slot_labels = {s.strftime("%H:%M"): s for s in slots}
        slot_cols = st.columns(min(len(slot_labels), 6))
        chosen_slot = None
        for col, (label, slot_dt) in zip(slot_cols * 10, slot_labels.items()):
            with col:
                if st.button(label, key=f"slot_{label}"):
                    chosen_slot = slot_dt

        if chosen_slot:
            st.session_state.bk_date = chosen_date
            st.session_state.bk_slot = chosen_slot
            st.session_state.bk_step = 4
            st.rerun()

    if st.button("Geri"):
        st.session_state.bk_step = 2
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Photo Upload & Confirm
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.bk_step == 4:
    shop   = st.session_state.bk_shop
    barber = st.session_state.bk_barber
    svc    = st.session_state.bk_service
    slot   = st.session_state.bk_slot
    dur    = int(svc.get("duration_minutes", svc.get("default_duration_minutes", 30)))
    price  = float(svc.get("price", svc.get("base_price", 0)))

    col_info, col_photo = st.columns([1, 1], gap="large")

    with col_info:
        st.subheader("Randevu Özeti")
        st.markdown(f"- **İşletme:** {shop['display_name']}")
        st.markdown(f"- **Berber:**  {barber['display_name']}")
        st.markdown(f"- **Hizmet:**  {svc['name']}")
        st.markdown(f"- **Tarih:**   {slot.strftime('%d.%m.%Y %H:%M')}")
        st.markdown(f"- **Süre:**    {dur} dakika")
        st.markdown(f"- **Ücret:**   {price:.2f} TL")

    with col_photo:
        st.subheader("Saç Referans Fotoğrafı (İsteğe Bağlı)")
        photo_file = st.file_uploader(
            "Fotoğraf yüklemek için tıklayın veya sürükleyin",
            type=["jpg", "jpeg", "png"],
            label_visibility="collapsed",
        )
        if photo_file:
            st.image(photo_file, caption="Yüklenen fotoğraf", use_column_width=True)
            st.session_state.bk_photo = photo_file

    st.divider()

    # reputation check
    allowed, rep_score = check_booking_allowed(user["id"])
    if not allowed:
        st.error(
            f"İtibar puanınız ({rep_score}/100) randevu almak için yetersiz. "
            f"Minimum puan: 40."
        )
    else:
        notes = st.text_area("Notlar (isteğe bağlı)", placeholder="Berber için not bırakabilirsiniz...")

        c1, c2 = st.columns(2)
        with c1:
            confirm = st.button("Randevuyu Onayla", type="primary", use_container_width=True)
        with c2:
            if st.button("Geri", use_container_width=True):
                st.session_state.bk_step = 3
                st.rerun()

        if confirm:
            with st.spinner("Randevu oluşturuluyor..."):
                try:
                    appt = create_appointment(
                        shop_id=shop["id"],
                        customer_person_id=user["id"],
                        barber_person_id=barber["person_id"],
                        service_id=svc["id"],
                        scheduled_start=slot,
                        duration_min=dur,
                        price=price,
                        customer_notes=notes,
                    )

                    # photo upload
                    if st.session_state.bk_photo:
                        photo_bytes = st.session_state.bk_photo.read()
                        upload_reference_photo(
                            appt["id"], shop["id"], user["id"],
                            photo_bytes, st.session_state.bk_photo.name,
                        )

                    # no-show prediction
                    rep     = get_reputation_profile(user["id"])
                    n_appts = rep["total_appointments_count"] or 1
                    n_ns    = rep["total_no_shows_count"]
                    days_ahead  = (slot.date() - date.today()).days
                    probability, model_v = predict_noshow(
                        reputation_score  = rep["reputation_score"],
                        no_show_rate      = n_ns / n_appts,
                        days_ahead        = days_ahead,
                        day_of_week       = slot.weekday(),
                        service_duration  = dur,
                    )
                    store_prediction(appt["id"], probability, model_v, {
                        "reputation_score": rep["reputation_score"],
                        "no_show_rate": n_ns / n_appts,
                        "days_ahead": days_ahead,
                    })

                    st.success(f"Randevunuz oluşturuldu! ({slot.strftime('%d.%m.%Y %H:%M')})")
                    if probability > 0.3:
                        st.warning(f"Hatırlatma: Randevu gelmeme tahmini yüksek (%{probability*100:.0f}). Lütfen zamanında gelin.")
                    reset_booking()
                    st.session_state.bk_confirmed = True
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

# ── confirmed ────────────────────────────────────────────────────────────────
if st.session_state.get("bk_confirmed"):
    st.balloons()
    st.success("Randevunuz başarıyla oluşturuldu!")
    if st.button("Yeni Randevu Al"):
        reset_booking()
        st.rerun()

# ── existing appointments ─────────────────────────────────────────────────────
st.divider()
st.subheader("Randevularım")
try:
    appts = get_customer_appointments(user["id"])
    if not appts:
        st.info("Henüz randevunuz yok.")
    else:
        status_tr = {
            "confirmed": "Onaylandı", "completed": "Tamamlandı",
            "no_show": "Gelmedi", "cancelled_by_customer": "İptal (Siz)",
            "cancelled_by_shop": "İptal (İşletme)", "pending": "Bekliyor",
            "late_cancel": "Geç İptal",
        }
        for a in appts:
            shop_name   = (a.get("shops") or {}).get("display_name", "—")
            barber_name = (a.get("persons") or {}).get("full_name", "—")
            start_str   = a["scheduled_start"][:16].replace("T", " ")
            status_str  = status_tr.get(a["status"], a["status"])
            price       = float(a["total_price_snapshot"])
            with st.expander(f"{start_str}  |  {shop_name}  |  {status_str}"):
                st.write(f"**Berber:** {barber_name}")
                st.write(f"**Ücret:** {price:.2f} TL")
                if a.get("customer_notes"):
                    st.write(f"**Not:** {a['customer_notes']}")
except Exception as e:
    st.error(f"Randevular yüklenemedi: {e}")
