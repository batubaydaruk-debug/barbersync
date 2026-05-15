"""Müşteri — İtibar skoru detay sayfası."""
from datetime import datetime

import streamlit as st

from db import list_my_appointments, reputation_for

# ── Auth ───────────────────────────────────────────────────────────────────────
user = st.session_state.get("user")
if not user:
    st.warning("Önce giriş yapmalısın.")
    st.page_link("app.py", label="Giriş sayfasına dön")
    st.stop()

if user["role"] != "customer":
    st.info("İtibar skoru yalnızca müşteri hesapları içindir.")
    st.stop()

st.title("İtibar Skorum")

rep   = reputation_for(user["id"])
score = rep["score"]
tier  = rep["tier"]

TIER_META = {
    "Güvenilir": ("#16a34a", "GÜVENİLİR",  "Harika! Berberlerin güvendiği müşterilerin arasındasın."),
    "Normal":    ("#2563eb", "NORMAL",      "İyi durumdayı. Randevularına sadık kalmaya devam et."),
    "Riskli":    ("#d97706", "RİSKLİ",     "Dikkat! Birkaç no-show seni sıkıntıya sokabilir."),
    "Kara liste":("#dc2626", "KARA LİSTE", "Randevu almanda kısıtlama olabilir. Skorunu iyileştir."),
    "Yeni":      ("#6b7280", "YENİ",       "Henüz randevu geçmişin yok. Başlamak için en iyi an!"),
}
color, badge_text, msg = TIER_META.get(tier, ("#6b7280", tier.upper(), ""))

# ── Skor kartı ─────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style='padding:28px 24px;border-radius:6px;background:{color}1A;
                border:2px solid {color};text-align:center;margin-bottom:16px'>
      <div style='font-size:11px;color:{color};font-weight:700;
                  letter-spacing:3px;text-transform:uppercase'>
        İTİBAR SKORUN
      </div>
      <div style='font-size:68px;font-weight:800;color:{color};line-height:1.1;
                  font-family:Inter,sans-serif'>
        {score}<span style='font-size:26px;opacity:.55'>/100</span>
      </div>
      <div style='font-size:15px;font-weight:700;color:{color};
                  letter-spacing:2px;margin-top:4px'>{badge_text}</div>
      <div style='font-size:13px;color:#888;margin-top:8px'>{msg}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.progress(score / 100)

# ── Metrikler ──────────────────────────────────────────────────────────────────
st.subheader("Geçmişin")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Toplam Randevu", rep["total_count"])
m2.metric("Tamamlanan", rep["completed_count"], delta=f"+{rep['completed_count'] * 2} puan")
m3.metric("Gelmedi (No-show)", rep["no_show_count"],
          delta=f"-{rep['no_show_count'] * 15} puan" if rep["no_show_count"] else None,
          delta_color="inverse")
m4.metric("Geç İptal", rep["late_cancel_count"],
          delta=f"-{rep['late_cancel_count'] * 5} puan" if rep["late_cancel_count"] else None,
          delta_color="inverse")

# ── Son randevular ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("Son Randevularım")

appts = list_my_appointments(user["id"], "customer")
if not appts:
    st.caption("Henüz randevu geçmişin yok.")
else:
    STATUS_TR = {
        "pending":   "Bekliyor",
        "confirmed": "Onaylı",
        "completed": "Tamamlandı",
        "cancelled": "İptal",
        "no_show":   "Gelmedi",
    }

    for a in appts[:10]:
        svc    = (a.get("services") or {}).get("name", "—")
        barber = (a.get("barber") or {}).get("full_name", "—")
        when   = datetime.fromisoformat(a["scheduled_start"].replace("Z", "+00:00"))
        tr     = STATUS_TR.get(a["status"], a["status"])

        st.markdown(
            f"**{when.strftime('%d.%m.%Y %H:%M')}** · {svc} · Berber: {barber} · _{tr}_"
        )

# ── Skor tablosu ───────────────────────────────────────────────────────────────
st.divider()
st.subheader("Skor Nasıl Hesaplanır?")

st.markdown("""
| Olay | Etki |
|---|---|
| Tamamlanan randevu | **+2 puan** |
| Gelmedi (no-show) | **−15 puan** |
| Geç iptal (randevuya 2 saatten az kala) | **−5 puan** |
""")

st.markdown("""
**Seviyeler**

| Skor | Seviye | Anlamı |
|---|---|---|
| 85–100 | Güvenilir | Berberlerin öncelik verdiği müşteri |
| 60–84  | Normal    | Standart akış |
| 30–59  | Riskli    | Berber önceden uyarılır |
| 0–29   | Kara Liste | Randevu engellenebilir |
| —      | Yeni      | Henüz randevu geçmişi yok |
""")
