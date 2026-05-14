import streamlit as st

st.title("BarberSync 💈")
st.subheader("Randevu Yönetimi")

menu = st.sidebar.selectbox("Menü", ["Randevu Al", "Randevuları Gör"])

if menu == "Randevu Al":
    st.header("Yeni Randevu")
    ad = st.text_input("Adınız")
    tarih = st.date_input("Tarih")
    saat = st.time_input("Saat")
    if st.button("Randevu Al"):
        if ad:
            st.success(f"{ad} için randevu alındı!")
        else:
            st.error("Lütfen adınızı girin.")

if menu == "Randevuları Gör":
    st.header("Mevcut Randevular")
    st.info("Henüz randevu yok.")