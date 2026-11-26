"""Global dashboard filter state, style and export helpers."""
import streamlit as st
from dashboard.export_utils import csv_bytes
from dashboard.filtering import normalize_filters


def apply_style():
    st.markdown("""<style>
    :root {--ink:#183247;--muted:#718497;--accent:#0f766e;--line:#e5edf1;--surface:#ffffff;}
    .block-container {padding-top: 1.25rem; padding-bottom: 3rem; max-width: 1500px;}
    h1, h2, h3 {letter-spacing: -0.035em; color: var(--ink);}
    h1 {font-weight:750;}
    h2 {border-left:3px solid var(--accent); padding-left:.65rem; margin-top:1.75rem;}
    [data-testid="stMetric"] {padding:.6rem .8rem; border:1px solid var(--line); border-radius:12px; background:linear-gradient(145deg,#fff,#f8fbfc); box-shadow:0 3px 12px #14364b0b;}
    [data-testid="stMetricLabel"] {color:var(--muted);font-weight:600;}
    [data-testid="stSidebar"] {background:#f4f8fa;border-right:1px solid var(--line);}
    [data-testid="stSidebar"] [role="radiogroup"] label {padding:.42rem .6rem;border-radius:9px;transition:background .18s ease,transform .18s ease;}
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {background:#e5f1f0;transform:translateX(2px);}
    [data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {border:1px solid var(--line);border-radius:13px;padding:.3rem;background:white;box-shadow:0 4px 18px #14364b08;}
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {animation:rise-in .38s ease both;}
    div[data-testid="stDownloadButton"] button {border-color:var(--accent);color:var(--accent);border-radius:9px;}
    div.stButton > button, div[data-testid="stFormSubmitButton"] button {border-radius:9px;font-weight:600;}
    .section-kicker {font-size:.75rem;text-transform:uppercase;letter-spacing:.12em;color:var(--accent);font-weight:700;margin-bottom:.25rem;}
    .flow-wrap {display:flex;align-items:stretch;gap:12px;margin:22px 0 28px;}
    .flow-step {flex:1;position:relative;background:linear-gradient(145deg,#fff,#f2f8f8);border:1px solid #dce9eb;border-radius:14px;padding:18px 16px;box-shadow:0 6px 18px #14364b0b;animation:flow-in .55s ease both;}
    .flow-step:nth-child(2){animation-delay:.12s}.flow-step:nth-child(3){animation-delay:.24s}.flow-step:nth-child(4){animation-delay:.36s}
    .flow-num {display:inline-grid;place-items:center;width:26px;height:26px;background:#dff3ef;color:#0f766e;border-radius:50%;font-weight:700;margin-bottom:10px;}
    .flow-title {font-weight:700;color:#183247}.flow-copy {font-size:.88rem;color:#718497;margin-top:5px;line-height:1.45}
    @keyframes rise-in {from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
    @keyframes flow-in {from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:translateY(0)}}
    @media (prefers-reduced-motion: reduce) {* {animation-duration:.01ms !important;transition-duration:.01ms !important;}}
    @media (max-width:760px) {.flow-wrap{flex-direction:column}.block-container{padding-left:1rem;padding-right:1rem}}
    </style>""", unsafe_allow_html=True)


def render_global_filters(options):
    st.sidebar.divider()
    st.sidebar.subheader("Global filters")
    min_date, max_date = options.get("min_date"), options.get("max_date")
    if min_date is None or max_date is None:
        st.sidebar.info("No order dates are available in PostgreSQL.")
        return {"start_date": None, "end_date": None, "city": None, "restaurant_id": None,
                "cuisine": None, "payment_method": None, "order_status": None}
    start_date = st.sidebar.date_input("From", value=min_date, min_value=min_date, max_value=max_date, key="global_from")
    end_date = st.sidebar.date_input("To", value=max_date, min_value=min_date, max_value=max_date, key="global_to")
    if start_date > end_date:
        st.sidebar.error("The start date must be on or before the end date.")
        start_date, end_date = min_date, max_date
    city = st.sidebar.selectbox("City", ["All", *(options.get("cities") or [])], key="global_city")
    restaurants = options.get("restaurants") or []
    restaurant_label = st.sidebar.selectbox("Restaurant", ["All", *restaurants], key="global_restaurant")
    cuisine = st.sidebar.selectbox("Cuisine", ["All", *(options.get("cuisines") or [])], key="global_cuisine")
    payment = st.sidebar.selectbox("Payment method", ["All", *(options.get("payment_methods") or [])], key="global_payment")
    status = st.sidebar.selectbox("Order status", ["All", *(options.get("statuses") or [])], key="global_status")
    return normalize_filters(start_date, end_date, city=city, restaurant_label=restaurant_label,
        cuisine=cuisine, payment_method=payment, order_status=status)


def download_csv(frame, label, filename, *, key=None):
    data = csv_bytes(frame)
    st.download_button(label, data, file_name=filename, mime="text/csv", key=key or filename,
        disabled=frame.empty, help="Exports the filtered rows currently returned from PostgreSQL.")
