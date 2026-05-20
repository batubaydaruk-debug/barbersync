"""BarberSync — Navigation entry point."""
import streamlit as st

st.set_page_config(
    page_title="BarberSync",
    page_icon="✂️",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown("""
<style>
    [data-testid="stSidebarContent"] { background: #16213e; }
    .stButton > button { border-radius: 6px; font-weight: 600; }
    .stButton > button[kind="primary"] {
        background: #1a1a2e; color: #fff; border: none;
    }
    .rep-score { font-size: 2.5rem; font-weight: 800; text-align: center; }
    .rep-green  { color: #28a745; }
    .rep-yellow { color: #ffc107; }
    .rep-red    { color: #dc3545; }
</style>
""", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.session_state.user = None

user = st.session_state.user
if user:
    role_label = {"customer": "Müşteri", "barber": "Berber", "owner": "İşletme Sahibi"}.get(
        user["primary_role"], user["primary_role"]
    )
    st.sidebar.markdown(f"**{user['full_name']}**")
    st.sidebar.caption(f"Rol: {role_label}")
    if st.sidebar.button("Çıkış Yap", key="btn_logout"):
        st.session_state.user = None
        st.rerun()

pg = st.navigation([
    st.Page("pages/Giris_Yap.py",         title="Giriş Yap",       icon="✂️"),
    st.Page("pages/1_Randevu_Al.py",      title="Randevu Al"),
    st.Page("pages/2_Berber_Programi.py", title="Berber Programım"),
    st.Page("pages/3_Envanter.py",         title="Envanter"),
    st.Page("pages/4_Sahip_Paneli.py",    title="Sahip Paneli"),
])
pg.run()
