"""
BarberSync — Screen 5: Shop Owner Dashboard
KPI overview, staff performance, revenue trend, customer reputations.
"""
import streamlit as st
from datetime import date
import pandas as pd

from modules.analytics import (
    get_shop_kpis, get_recent_appointments,
    get_staff_performance, get_revenue_trend,
)
from utils.tz import fmt_tr
from modules.reputation import list_customer_reputations
from modules.auth import register_barber_to_shop

# ── auth guard ────────────────────────────────────────────────────────────────
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("Bu sayfayı görüntülemek için giriş yapmanız gerekiyor.")
    st.stop()

user = st.session_state.user
if user["primary_role"] != "owner":
    st.warning("Bu sayfa yalnızca işletme sahipleri içindir.")
    st.stop()

shop_id = user.get("shop_id")
if not shop_id:
    st.error("Bu hesaba bağlı bir işletme bulunamadı. Ana sayfadan işletme oluşturun.")
    st.stop()

st.title("Sahip Paneli")

# ─────────────────────────────────────────────────────────────────────────────
# KPI strip
# ─────────────────────────────────────────────────────────────────────────────
try:
    kpis = get_shop_kpis(shop_id)
except Exception as e:
    st.error(f"KPI'lar yüklenemedi: {e}")
    kpis = {}

if kpis:
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Bugünkü Randevu",  kpis.get("total_today", 0))
    k2.metric("Tamamlanan",        kpis.get("completed_today", 0))
    k3.metric("No-Show Oranı",     f"%{kpis.get('no_show_rate', 0.0)}")
    k4.metric("Günlük Ciro",       f"{kpis.get('revenue_today', 0.0):.2f} TL")
    k5.metric("Düşük Stok",        kpis.get("low_stock_count", 0))

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────────────
tab_appts, tab_staff, tab_revenue, tab_reps, tab_barbers = st.tabs([
    "Son Randevular", "Personel Performansı", "Gelir Trendi",
    "Müşteri İtibarları", "Berber Ekle",
])

# ── Tab 1: Recent Appointments ───────────────────────────────────────────────
with tab_appts:
    try:
        recent = get_recent_appointments(shop_id, limit=20)
    except Exception as e:
        st.error(f"Randevular yüklenemedi: {e}")
        recent = []

    if not recent:
        st.info("Henüz randevu yok.")
    else:
        status_tr = {
            "confirmed":           "Onaylandı",
            "completed":           "Tamamlandı",
            "no_show":             "Gelmedi",
            "cancelled_by_customer": "İptal (Müşteri)",
            "cancelled_by_shop":   "İptal (İşletme)",
            "pending":             "Bekliyor",
            "late_cancel":         "Geç İptal",
        }
        rows = []
        for a in recent:
            rows.append({
                "Tarih":    fmt_tr(a["scheduled_start"]),
                "Müşteri":  a.get("customer_name", "—"),
                "Berber":   a.get("barber_name", "—"),
                "Durum":    status_tr.get(a["status"], a["status"]),
                "Ücret":    f"{float(a['total_price_snapshot']):.2f} TL",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── Tab 2: Staff Performance ─────────────────────────────────────────────────
with tab_staff:
    col_y, col_m = st.columns(2)
    with col_y:
        sel_year  = st.number_input("Yıl",  min_value=2020, max_value=date.today().year, value=date.today().year)
    with col_m:
        sel_month = st.number_input("Ay",   min_value=1, max_value=12, value=date.today().month)

    try:
        perf = get_staff_performance(shop_id, int(sel_year), int(sel_month))
    except Exception as e:
        st.error(f"Performans yüklenemedi: {e}")
        perf = []

    if not perf:
        st.info("Bu dönem için veri bulunamadı.")
    else:
        rows = []
        for p in perf:
            rows.append({
                "Berber":          p.get("barber_name", "—"),
                "Tamamlanan":      p.get("appointments_completed", 0),
                "Planlanan":       p.get("appointments_scheduled", 0),
                "Gelir (TL)":      f"{p.get('total_revenue', 0.0):.2f}",
                "No-Show Oranı":   f"%{p.get('no_show_rate', 0)*100:.1f}",
                "İptal Oranı":     f"%{p.get('cancellation_rate', 0)*100:.1f}",
                "Ort. Puan":       p.get("average_rating") or "—",
                "Prim Hakkı":      "✅" if p.get("is_bonus_eligible") else "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("Prim hakkı: ≥30 tamamlanan randevu, ≤%5 no-show, ≥4.0 ortalama puan")

# ── Tab 3: Revenue Trend ─────────────────────────────────────────────────────
with tab_revenue:
    days_opt = st.selectbox("Dönem", [7, 14, 30, 60, 90], index=2, format_func=lambda d: f"Son {d} gün")
    try:
        trend = get_revenue_trend(shop_id, days=days_opt)
    except Exception as e:
        st.error(f"Gelir verisi yüklenemedi: {e}")
        trend = []

    if not trend:
        st.info("Bu dönemde tamamlanan randevu bulunamadı.")
    else:
        try:
            import plotly.express as px
            df_trend = pd.DataFrame(trend)
            fig = px.bar(
                df_trend, x="date", y="revenue",
                labels={"date": "Tarih", "revenue": "Gelir (TL)"},
                title=f"Son {days_opt} Gün Günlük Gelir",
                color_discrete_sequence=["#c9a84c"],
            )
            fig.update_layout(
                plot_bgcolor="#1a1a2e",
                paper_bgcolor="#1a1a2e",
                font_color="#e8e8e8",
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            df_trend = pd.DataFrame(trend).set_index("date")
            st.bar_chart(df_trend["revenue"])

# ── Tab 4: Customer Reputations ──────────────────────────────────────────────
with tab_reps:
    try:
        reps = list_customer_reputations(shop_id)
    except Exception as e:
        st.error(f"İtibar verileri yüklenemedi: {e}")
        reps = []

    if not reps:
        st.info("Henüz müşteri verisi yok.")
    else:
        search = st.text_input("Müşteri Ara", placeholder="İsim veya e-posta...")
        if search:
            def _matches(r):
                p = r.get("persons") or {}
                return search.lower() in (p.get("full_name","") + p.get("email","")).lower()
            reps = [r for r in reps if _matches(r)]

        rows = []
        for r in reps:
            score  = r.get("reputation_score", 0)
            tier   = "Yeşil" if score >= 80 else ("Sarı" if score >= 50 else "Kırmızı")
            person = r.get("persons") or {}
            rows.append({
                "Müşteri":         person.get("full_name", "—"),
                "Puan":            score,
                "Seviye":          tier,
                "Toplam Randevu":  r.get("total_appointments_count", 0),
                "No-Show":         r.get("total_no_shows_count", 0),
            })

        df_reps = pd.DataFrame(rows)
        def color_tier(val):
            colors = {"Yeşil": "color: #28a745", "Sarı": "color: #ffc107", "Kırmızı": "color: #dc3545"}
            return colors.get(val, "")

        try:
            styled = df_reps.style.map(color_tier, subset=["Seviye"])
        except AttributeError:
            styled = df_reps.style.applymap(color_tier, subset=["Seviye"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

# ── Tab 5: Add Barber ────────────────────────────────────────────────────────
with tab_barbers:
    st.subheader("Berberi İşletmeye Ekle")
    st.caption("Berber rolüyle kayıt olan bir kullanıcının e-postasını girerek işletmenize bağlayabilirsiniz.")

    from db.connection import get_client

    with st.form("form_add_barber"):
        barber_email = st.text_input("Berber E-postası")
        display_name = st.text_input("Görünen İsim (isteğe bağlı)")
        add_submitted = st.form_submit_button("Berberi Ekle", type="primary")

    if add_submitted:
        if not barber_email:
            st.error("E-posta zorunludur.")
        else:
            try:
                sb = get_client()
                person = (
                    sb.table("persons")
                    .select("id, full_name, primary_role")
                    .eq("email", barber_email.strip().lower())
                    .single()
                    .execute()
                    .data
                )
                if not person:
                    st.error("Bu e-posta ile kayıtlı kullanıcı bulunamadı.")
                elif person["primary_role"] != "barber":
                    st.error("Bu kullanıcı berber rolüyle kayıtlı değil.")
                else:
                    register_barber_to_shop(person["id"], shop_id)
                    st.success(f"{person['full_name']} işletmenize eklendi.")
            except Exception as exc:
                st.error(str(exc))
