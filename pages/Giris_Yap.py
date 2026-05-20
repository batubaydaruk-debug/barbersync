"""BarberSync — Giriş / Kayıt sayfası."""
import streamlit as st
from modules.auth import login_user, register_user, create_shop_for_owner, get_shop_for_owner


def _show_auth():
    st.markdown("## ✂️ BarberSync")
    st.caption("Berber Randevu ve Yönetim Sistemi")
    st.divider()

    col_login, col_register = st.columns(2, gap="large")

    with col_login:
        st.subheader("Giriş Yap")
        with st.form("form_login"):
            email    = st.text_input("E-posta")
            password = st.text_input("Şifre", type="password")
            ok = st.form_submit_button("Giriş Yap", use_container_width=True, type="primary")

        if ok:
            if not email or not password:
                st.error("E-posta ve şifre zorunludur.")
            else:
                try:
                    user = login_user(email, password)
                    st.session_state.user = user
                    st.rerun()
                except (ValueError, Exception) as exc:
                    st.error(str(exc))

    with col_register:
        st.subheader("Kayıt Ol")
        with st.form("form_register"):
            full_name  = st.text_input("Ad Soyad")
            email_r    = st.text_input("E-posta", key="reg_email")
            phone      = st.text_input("Telefon", placeholder="+90 5XX XXX XX XX")
            password_r = st.text_input("Şifre (min. 6 karakter)", type="password", key="reg_pass")
            role       = st.selectbox(
                "Rol",
                ["customer", "barber", "owner"],
                format_func=lambda x: {
                    "customer": "Müşteri",
                    "barber":   "Berber",
                    "owner":    "İşletme Sahibi",
                }[x],
            )
            kvkk = st.checkbox("KVKK Gizlilik Bildirimi'ni okudum ve kabul ediyorum")
            ok_r = st.form_submit_button("Hesap Oluştur", use_container_width=True, type="primary")

        if ok_r:
            if not full_name or not email_r or not phone or not password_r:
                st.error("Tüm alanlar zorunludur.")
            elif not kvkk:
                st.error("KVKK bildirimi kabul edilmelidir.")
            else:
                try:
                    register_user(full_name, email_r, phone, password_r, role, kvkk)
                    st.success("Hesap oluşturuldu! Giriş yapabilirsiniz.")
                except (ValueError, Exception) as exc:
                    st.error(str(exc))


def _show_home():
    user = st.session_state.user
    role = user["primary_role"]

    if role == "owner" and not user.get("shop_id"):
        existing_shop = get_shop_for_owner(user["id"])
        if existing_shop:
            st.session_state.user["shop_id"] = existing_shop["id"]
            st.rerun()
        else:
            st.subheader("İşletmenizi oluşturun")
            with st.form("form_create_shop"):
                shop_name  = st.text_input("İşletme adı (görünen)")
                legal_name = st.text_input("Ticaret unvanı", placeholder="Zorunlu değil")
                city       = st.text_input("Şehir")
                address    = st.text_input("Adres")
                ok_shop    = st.form_submit_button("İşletmeyi Oluştur", type="primary")
            if ok_shop:
                if not shop_name:
                    st.error("İşletme adı zorunludur.")
                else:
                    try:
                        shop = create_shop_for_owner(
                            user["id"], shop_name, legal_name or shop_name, city, address
                        )
                        st.session_state.user["shop_id"] = shop["id"]
                        st.success(f"'{shop_name}' işletmesi oluşturuldu!")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            return

    role_label = {
        "customer": "Randevu Al",
        "barber":   "Berber Programım",
        "owner":    "Sahip Paneli",
    }

    st.markdown(f"### Hoş geldiniz, {user['full_name']}!")
    st.info(f"Sol menüden **{role_label.get(role, '')}** sayfasına gidin.")

    if role == "customer":
        from modules.reputation import get_reputation_profile
        try:
            rep   = get_reputation_profile(user["id"])
            score = rep["reputation_score"]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("İtibar Puanı", f"{score}/100")
            with col2:
                st.metric("Toplam Randevu", rep["total_appointments_count"])
            with col3:
                st.metric("No-Show Sayısı", rep["total_no_shows_count"])
        except Exception:
            pass


if st.session_state.user is None:
    _show_auth()
else:
    _show_home()
