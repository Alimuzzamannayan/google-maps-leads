import streamlit as st
import sqlite3
import pandas as pd
import os
import re
import subprocess
import sys
from streamlit_autorefresh import st_autorefresh
import datetime

st.set_page_config(page_title="Business Leads Dashboard", page_icon="🏢", layout="wide")

# Tailwind CSS - Compact & Smooth
st.markdown("""
<!-- Tailwind CSS -->
<script src="https://cdn.tailwindcss.com"></script>
<style>
/* Compact spacing */
.block-container { padding-top: 0.5rem; padding-bottom: 0.5rem; }
/* Smooth transitions */
.stButton>button, .stSelectbox>div>div>div, .stTextInput>div>div>input { transition: all 0.2s ease; }
/* Mobile optimizations */
@media (max-width: 768px) {
    .stButton>button { min-height: 44px; padding: 0.5rem 0.75rem; font-size: 0.9rem; }
    .stSelectbox>div>div>div, .stTextInput>div>div>input { min-height: 44px; }
    [data-testid="stSidebar"] { width: 85% !important; max-width: 300px; }
    .bottom-nav { display: flex; }
    div[data-testid="stMetric"] { padding: 0.5rem; }
    div[data-testid="stMetric"] label { font-size: 0.7rem; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { font-size: 1.2rem; }
}
/* Desktop hide mobile */
@media (min-width: 769px) {
    .mobile-only, .bottom-nav { display: none !important; }
}
/* Bottom nav */
.bottom-nav {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: white; box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
    z-index: 999; padding: 0.5rem;
    justify-content: space-around; display: none;
}
.bottom-nav a {
    display: flex; flex-direction: column; align-items: center;
    padding: 0.5rem; color: #6b7280; text-decoration: none; font-size: 0.7rem;
}
.bottom-nav a.active { color: #3b82f6; }
/* Status badges */
.status-dot {
    display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px;
}
.status-running { background: #22c55e; }
.status-idle { background: #9ca3af; }
.status-error { background: #ef4444; }
/* Tags */
.tag {
    display: inline-block; padding: 0.25rem 0.6rem;
    border-radius: 9999px; font-size: 0.75rem; font-weight: 600;
    margin: 2px;
}
.tag-blue { background: #dbeafe; color: #1d4ed8; }
.tag-green { background: #dcfce7; color: #16a34a; }
.tag-yellow { background: #fef3c7; color: #d97706; }
.tag-purple { background: #f3e8ff; color: #9333ea; }
</style>
""", unsafe_allow_html=True)

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

def get_time_info():
    if not os.path.exists(DB_PATH):
        return None, None, None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT last_updated FROM scraper_status WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            last_updated = datetime.datetime.fromisoformat(row[0])
            local_tz = datetime.timezone(datetime.timedelta(hours=5))
            last_updated_local = last_updated.replace(tzinfo=datetime.timezone.utc).astimezone(local_tz)
            next_run = last_updated + datetime.timedelta(hours=72)
            next_run_local = next_run.replace(tzinfo=datetime.timezone.utc).astimezone(local_tz)
            now = datetime.datetime.now(local_tz)
            time_remaining = next_run_local - now
            if time_remaining.total_seconds() < 0:
                time_remaining_text = "Overdue!"
            else:
                hours = int(time_remaining.total_seconds() // 3600)
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                time_remaining_text = f"{hours}h {minutes}m"
            return last_updated_local, next_run_local, time_remaining_text
    except Exception:
        pass
    return None, None, None

def load_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM leads", conn)
        conn.close()
        if not df.empty and 'name' in df.columns and 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df.sort_values('timestamp', ascending=False)
            df = df.drop_duplicates(subset=['name'], keep='first')
            df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
        return df
    except Exception:
        return pd.DataFrame()

def load_status():
    if not os.path.exists(DB_PATH):
        return "Waiting...", None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT status, last_updated FROM scraper_status WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0] if row[0] else "No status", row[1]
        return "No record", None
    except Exception:
        return "Error", None

def extract_coords(address):
    if not address or pd.isna(address): return None, None
    pattern = r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)"
    match = re.search(pattern, str(address))
    if match:
        try:
            lat, lon = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180: return lat, lon
        except Exception: pass
    return None, None

# Load data
df = load_data()
status_text, _ = load_status()

# Auto refresh
scraper_running = any(x in status_text for x in ["Crawling", "Running", "Scrolling", "Extracting", "Attempt", "Job Started"])
if scraper_running:
    st_autorefresh(interval=30000, limit=None, key="refresh")

# Mobile header
st.markdown("""
<div class="mobile-only flex items-center justify-between px-3 py-2 bg-white shadow-sm sticky top-0" style="margin: -1rem -1rem 1rem -1rem;">
    <div class="flex items-center gap-2">
        <button onclick="document.querySelector('[data-testid=\\'stSidebar\\']').setAttribute('aria-expanded', 'true')" class="p-1">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
        </button>
        <span class="font-bold">🏢 Leads</span>
    </div>
    <span class="text-xs text-gray-500">Maldives</span>
</div>
""", unsafe_allow_html=True)

st.title("🏢 Business Leads")
st.caption("📍 Google Maps • Maldives")

# Sidebar
with st.sidebar:
    st.header("🚀 Scraper")
    
    # Compact status
    if "Error" in status_text or "Failed" in status_text:
        st.markdown(f'<div class="flex items-center text-red-600 font-medium"><span class="status-dot status-error"></span>{status_text[:25]}</div>', unsafe_allow_html=True)
        is_running = False
    elif any(x in status_text for x in ["Sleeping", "Idle", "Stopped"]):
        st.markdown(f'<div class="flex items-center text-gray-500 font-medium"><span class="status-dot status-idle"></span>{status_text[:25]}</div>', unsafe_allow_html=True)
        is_running = False
    else:
        st.markdown(f'<div class="flex items-center text-green-600 font-medium"><span class="status-dot status-running"></span>{status_text[:25]}</div>', unsafe_allow_html=True)
        is_running = True
    
    # Compact time info
    lu, nr, tr = get_time_info()
    if lu:
        st.markdown(f"""
        <div class="mt-3 space-y-2">
            <div class="text-xs text-gray-500">Last Updated</div>
            <div class="font-semibold text-sm">{lu.strftime('%d %b %H:%M')}</div>
            <div class="text-xs text-gray-500">Next Run</div>
            <div class="font-semibold text-sm">{nr.strftime('%d %b %H:%M')}</div>
            <div class="text-xs text-gray-500">Countdown</div>
            <div class="font-bold text-blue-600">{tr}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Compact buttons
    c1, c2 = st.columns(2)
    if c1.button("▶️ Start", disabled=is_running, width='stretch'):
        try:
            subprocess.Popen([sys.executable, "scraper.py", "run"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            st.toast("Started! 🚀")
            st.rerun()
        except Exception:
            st.error("Failed")
    if c2.button("🔄 Refresh", width='stretch'):
        st.rerun()
    
    st.markdown("---")
    st.header("🔍 Filters")
    
    # Filter options
    locations = sorted(df['country'].dropna().unique().tolist()) if 'country' in df.columns else []
    if locations: locations.insert(0, "All")
    selected_location = st.selectbox("Country", locations, index=0)
    
    queries = sorted(df['query'].dropna().unique().tolist()) if 'query' in df.columns else []
    if queries: queries.insert(0, "All")
    selected_query = st.selectbox("Category", queries, index=0)
    
    search_name = st.text_input("Search", placeholder="Business name...")
    
    # Contact filters
    with st.expander("📱 Contacts"):
        phone_filter = st.radio("Phone", ["All", "Has Phone", "No Phone"], horizontal=True, index=0)
        email_filter = st.radio("Email", ["All", "Has Email", "No Email"], horizontal=True, index=0)
        web_filter = st.radio("Website", ["All", "Has Website", "No Website"], horizontal=True, index=0)
    
    st.metric("Leads", len(df))

if df.empty:
    st.warning("No data. Run scraper first.")
    st.stop()

# Extract coords
coords = df['address'].apply(extract_coords)
df['latitude'] = coords.apply(lambda x: x[0])
df['longitude'] = coords.apply(lambda x: x[1])

# Stats - using native Streamlit metrics for better visibility
total = len(df)
with_phone = len(df[df['phone'].notna() & (df['phone'] != 'N/A') & (df['phone'] != '')]) if 'phone' in df.columns else 0
with_email = len(df[df['email'].notna() & (df['email'] != 'N/A') & (df['email'] != '')]) if 'email' in df.columns else 0
with_web = len(df[df['website'].notna() & (df['website'] != 'N/A') & (df['website'] != '')]) if 'website' in df.columns else 0

st.markdown("### 📊 Overview")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Leads", total)
c2.metric("📱 Phone", with_phone)
c3.metric("📧 Email", with_email)
c4.metric("🌐 Website", with_web)

# Category tags
if 'query' in df.columns:
    tags = df['query'].value_counts().head(6)
    tag_html = '<div class="flex flex-wrap gap-1 mb-3">'
    colors = ['tag-blue', 'tag-green', 'tag-yellow', 'tag-purple']
    for i, (cat, cnt) in enumerate(tags.items()):
        tag_html += f'<span class="tag {colors[i%4]}">{cat}: {cnt}</span>'
    tag_html += '</div>'
    st.markdown(tag_html, unsafe_allow_html=True)

# Apply filters
fdf = df.copy()
if selected_location != "All" and 'country' in df.columns:
    fdf = fdf[fdf['country'] == selected_location]
if selected_query != "All" and 'query' in df.columns:
    fdf = fdf[fdf['query'] == selected_query]
if search_name and 'name' in df.columns:
    fdf = fdf[fdf['name'].str.contains(search_name, case=False, na=False)]

if phone_filter == "Has Phone":
    fdf = fdf[fdf['phone'].notna() & (fdf['phone'] != 'N/A') & (fdf['phone'] != '')]
elif phone_filter == "No Phone":
    fdf = fdf[(fdf['phone'].isna()) | (fdf['phone'] == 'N/A') | (fdf['phone'] == '')]

if email_filter == "Has Email":
    fdf = fdf[fdf['email'].notna() & (fdf['email'] != 'N/A') & (fdf['email'] != '')]
elif email_filter == "No Email":
    fdf = fdf[(fdf['email'].isna()) | (fdf['email'] == 'N/A') | (fdf['email'] == '')]

if web_filter == "Has Website":
    fdf = fdf[fdf['website'].notna() & (fdf['website'] != 'N/A') & (fdf['website'] != '')]
elif web_filter == "No Website":
    fdf = fdf[(fdf['website'].isna()) | (fdf['website'] == 'N/A') | (fdf['website'] == '')]

# Tabs
tab1, tab2, tab3 = st.tabs(["📋 Data", "📊 Analysis", "🗺️ Map"])
with tab1:
    cols = [c for c in ['name', 'rating', 'category', 'address', 'phone', 'email', 'website', 'timestamp'] if c in fdf.columns]
    st.dataframe(fdf[cols], width='stretch', hide_index=True, height=400)
with tab2:
    if 'category' in fdf.columns and not fdf.empty:
        counts = fdf['category'].value_counts().reset_index()
        counts.columns = ['Category', 'Count']
        st.bar_chart(counts.set_index('Category')['Count'], width='stretch')
with tab3:
    mdf = fdf.dropna(subset=['latitude', 'longitude'])
    if not mdf.empty:
        st.map(mdf, width='stretch')
    else:
        st.info("No coordinates found")

# Bottom nav
st.markdown("""
<div class="bottom-nav">
    <a href="#" class="active">📋<br><span>Data</span></a>
    <a href="#">📊<br><span>Stats</span></a>
    <a href="#">🗺️<br><span>Map</span></a>
    <a href="#">⚙️<br><span>More</span></a>
</div>
""", unsafe_allow_html=True)
