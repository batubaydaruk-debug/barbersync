"""Shared UI theme — MrBarberPrivate: burgundy/anthracite corporate aesthetic."""
import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
@import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css');

:root {
  --burgundy:     #4A0404;
  --burgundy-lt:  #6B0606;
  --burgundy-dim: rgba(74,4,4,.2);
  --anthracite:   #2C2C2C;
  --grey:         #8E8E8E;
  --bone:         #F5F5F5;
  --bg:           #080101;
  --card:         #111111;
  --border:       rgba(255,255,255,.09);
  --text:         #EDEAE6;
  --muted:        #8E8E8E;
  --r:            5px;
  --r-sm:         4px;
  --r-lg:         6px;
}

.stApp,
[data-testid="stAppViewContainer"] {
  background: #080101 !important;
  font-family: 'Inter', sans-serif !important;
  color: var(--text) !important;
}

.main .block-container {
  padding: 1.8rem 2rem 3rem !important;
  max-width: 960px;
  margin: auto;
}

[data-testid="stSidebar"] {
  background: #0D0101 !important;
  border-right: 1px solid rgba(74,4,4,.3) !important;
}
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] { background: transparent !important; }

h1, h2, h3 {
  font-family: 'Inter', sans-serif !important;
  letter-spacing: .3px !important;
  color: var(--bone) !important;
  font-weight: 700 !important;
}
h1 { font-size: 1.9rem !important; }
h2 { font-size: 1.35rem !important; }
h3 { font-size: 1.05rem !important; }
p, li, label, span { color: var(--text) !important; }

[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--card) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-lg) !important;
  transition: border-color .2s ease !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
  border-color: rgba(74,4,4,.45) !important;
}

[data-testid="stMetric"] {
  background: var(--card) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-lg) !important;
  padding: 16px !important;
}
[data-testid="stMetricValue"] {
  color: var(--bone) !important;
  font-size: 1.85rem !important;
  font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
  color: var(--grey) !important;
  font-size: .72rem !important;
  letter-spacing: 1px !important;
  text-transform: uppercase !important;
}
[data-testid="stMetricDelta"] { font-size: .78rem !important; }

[data-testid="baseButton-primary"],
[data-testid="baseButton-primaryFormSubmit"] {
  background: var(--burgundy) !important;
  color: var(--bone) !important;
  border: 1px solid var(--burgundy-lt) !important;
  border-radius: var(--r) !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 600 !important;
  letter-spacing: .2px !important;
  transition: background .2s ease, border-color .2s ease !important;
}
[data-testid="baseButton-primary"]:hover,
[data-testid="baseButton-primaryFormSubmit"]:hover {
  background: var(--burgundy-lt) !important;
  border-color: #8B0A0A !important;
}

[data-testid="baseButton-secondary"],
.stButton > button {
  background: #181818 !important;
  color: var(--grey) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 500 !important;
  transition: color .2s ease, border-color .2s ease !important;
}
[data-testid="baseButton-secondary"]:hover,
.stButton > button:hover {
  color: var(--bone) !important;
  border-color: rgba(255,255,255,.2) !important;
}

[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
  background: #111111 !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  color: var(--text) !important;
  font-family: 'Inter', sans-serif !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: var(--burgundy-lt) !important;
  box-shadow: 0 0 0 2px rgba(74,4,4,.22) !important;
  outline: none !important;
}

[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div {
  background: #111111 !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  color: var(--text) !important;
}
[data-baseweb="popover"] { background: #1A1A1A !important; }
[data-baseweb="menu"] li { color: var(--text) !important; }
[data-baseweb="menu"] li:hover { background: var(--burgundy-dim) !important; }

.stTabs [data-baseweb="tab-list"] {
  background: #111111 !important;
  border-radius: var(--r) !important;
  padding: 3px !important;
  border: 1px solid var(--border) !important;
  gap: 2px !important;
}
.stTabs [data-baseweb="tab"] {
  color: var(--grey) !important;
  border-radius: var(--r-sm) !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 500 !important;
  font-size: .87rem !important;
  border: none !important;
  background: transparent !important;
}
.stTabs [aria-selected="true"] {
  background: var(--burgundy) !important;
  color: var(--bone) !important;
  font-weight: 600 !important;
}
[data-baseweb="tab-highlight"],
[data-baseweb="tab-border"] { display: none !important; }

[data-testid="stProgressBar"] > div {
  background: rgba(255,255,255,.07) !important;
  border-radius: 3px !important;
  height: 8px !important;
}
[data-testid="stProgressBar"] > div > div {
  background: var(--burgundy) !important;
  border-radius: 3px !important;
}

[data-testid="stDateInput"] input {
  background: #111111 !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  color: var(--text) !important;
}

[data-testid="stSlider"] [data-baseweb="thumb"] {
  background: var(--burgundy) !important;
  border: 2px solid var(--burgundy-lt) !important;
}
[data-testid="stSlider"] [data-baseweb="track-foreground"] {
  background: var(--burgundy) !important;
}

hr {
  border: none !important;
  border-top: 1px solid rgba(255,255,255,.07) !important;
  margin: 1.2rem 0 !important;
}

[data-testid="stAlert"] { border-radius: var(--r) !important; }

[data-testid="stCaptionContainer"] p,
.stCaption { color: var(--grey) !important; font-size: .83rem !important; }

[data-testid="stForm"] {
  background: #111111 !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-lg) !important;
  padding: 20px !important;
}

[data-testid="stNumberInput"] button {
  background: #181818 !important;
  border-color: var(--border) !important;
  color: var(--grey) !important;
}

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(74,4,4,.45); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(74,4,4,.7); }
</style>
"""


def apply_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def icon(name: str, style: str = "") -> str:
    s = f' style="{style}"' if style else ""
    return f'<i class="fa-solid fa-{name}"{s}></i>'
