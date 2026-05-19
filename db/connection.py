import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


def get_client() -> Client:
    """Return a Supabase client, reading credentials from st.secrets or .env."""
    try:
        import streamlit as st
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
    except Exception:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")

    if not url or not key:
        raise RuntimeError(
            "Supabase kimlik bilgileri bulunamadı. "
            ".env dosyasını veya .streamlit/secrets.toml dosyasını kontrol edin."
        )
    return create_client(url, key)
