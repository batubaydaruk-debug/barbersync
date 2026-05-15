"""BarberSync — gateway entry point with role-based navigation."""
import streamlit as st

from _theme import apply_theme, icon
from db import login_user, register_user

st.set_page_config(
    page_title="BarberSync",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

if "user" not in st.session_state:
    st.session_state.user = None

user = st.session_state.user

# ── Gateway: hide sidebar, show auth form ─────────────────────────────────────
if not user:
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] { display: none !important; }
    [data-testid="stSidebarNav"]     { display: none !important; }
    .main .block-container { max-width: 460px !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style='text-align:center;padding:3rem 0 2rem'>
      <div style='font-size:2rem;color:#4A0404;margin-bottom:10px'>
        {icon('scissors')}
      </div>
      <div style='font-size:1.9rem;font-weight:800;letter-spacing:6px;
                  color:#F5F5F5;font-family:Inter,sans-serif'>
        BARBERSYNC
      </div>
      <div style='font-size:.65rem;letter-spacing:4px;color:#8E8E8E;
                  text-transform:uppercase;margin-top:6px'>
        Berber Yönetim Sistemi
      </div>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["Giriş Yap", "Kayıt Ol"])

    with tab_login:
        email  = st.text_input("E-posta", key="l_email", placeholder="ornek@email.com")
        passwd = st.text_input("Şifre",   key="l_pass",  type="password")
        if st.button("Giriş Yap", key="btn_login", type="primary", use_container_width=True):
            if not email or not passwd:
                st.error("Tüm alanları doldurun.")
            else:
                user_obj, err = login_user(email.strip().lower(), passwd)
                if err:
                    st.error(err)
                else:
                    st.session_state.user = user_obj
                    st.rerun()

    with tab_register:
        full_name = st.text_input("Ad Soyad",     key="r_name")
        r_email   = st.text_input("E-posta",      key="r_email")
        r_phone   = st.text_input("Telefon",      key="r_phone", placeholder="+90 555 000 00 00")
        r_role    = st.selectbox(
            "Rol", ["customer", "barber", "owner"],
            format_func=lambda x: {
                "customer": "Müşteri",
                "barber":   "Berber",
                "owner":    "İşletme Sahibi",
            }[x],
        )
        r_pass  = st.text_input("Şifre",        key="r_pass",  type="password")
        r_pass2 = st.text_input("Şifre Tekrar", key="r_pass2", type="password")
        st.caption("Kayıt olarak KVKK Gizlilik Politikamızı kabul etmiş olursunuz.")

        if st.button("Kayıt Ol", key="btn_reg", type="primary", use_container_width=True):
            if not all([full_name, r_email, r_phone, r_pass, r_pass2]):
                st.error("Tüm alanları doldurun.")
            elif len(r_pass) < 8:
                st.error("Şifre en az 8 karakter olmalı.")
            elif r_pass != r_pass2:
                st.error("Şifreler eşleşmiyor.")
            else:
                user_obj, err = register_user(
                    full_name, r_email.strip().lower(), r_phone, r_pass, r_role
                )
                if err:
                    st.error(err)
                else:
                    st.success("Kayıt başarılı! Şimdi giriş yapabilirsiniz.")

    st.stop()

# ── Logged in: role-based navigation ─────────────────────────────────────────
role = user.get("role", "customer")

PAGES_BY_ROLE = {
    "customer": [
        st.Page("pages/1_Randevu_Al.py",    title="Randevu Al",    icon=":material/calendar_month:"),
        st.Page("pages/3_Itibar_Skorum.py", title="İtibar Skorum", icon=":material/star:"),
    ],
    "barber": [
        st.Page("pages/2_Berber_Paneli.py", title="Berber Paneli", icon=":material/content_cut:"),
    ],
    "owner": [
        st.Page("pages/2_Berber_Paneli.py", title="Berber Paneli", icon=":material/content_cut:"),
        st.Page("pages/1_Randevu_Al.py",    title="Randevu Al",    icon=":material/calendar_month:"),
        st.Page("pages/3_Itibar_Skorum.py", title="İtibar Skorum", icon=":material/star:"),
    ],
}

pages = PAGES_BY_ROLE.get(role, PAGES_BY_ROLE["customer"])

ROLE_TR = {"customer": "Müşteri", "barber": "Berber", "owner": "İşletme Sahibi"}
ROLE_FA = {"customer": "user",    "barber": "scissors", "owner": "store"}

with st.sidebar:
    st.markdown(f"""
    <div style='padding:16px 4px 8px'>
      <div style='font-size:.62rem;letter-spacing:3px;color:#8E8E8E;
                  text-transform:uppercase;margin-bottom:6px'>
        {ROLE_TR.get(role, role)}
      </div>
      <div style='font-size:.93rem;font-weight:600;color:#F5F5F5'>
        {icon(ROLE_FA.get(role, 'user'), 'color:#6B0606;margin-right:8px')}
        {user['full_name']}
      </div>
    </div>
    <hr style='border-color:rgba(74,4,4,.3);margin:0 0 10px'>
    """, unsafe_allow_html=True)

    if st.button("Çıkış Yap", use_container_width=True):
        st.session_state.user = None
        st.rerun()

pg = st.navigation(pages)
pg.run()
