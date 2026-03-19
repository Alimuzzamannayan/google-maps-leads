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

# Inject FlyonUI and custom responsive CSS
st.markdown("""
<!-- FlyonUI CSS -->
<link href="https://cdn.jsdelivr.net/npm/flyonui@latest/dist/css/flyonui.min.css" rel="stylesheet">
<!-- Tailwind CSS (required for FlyonUI) -->
<script src="https://cdn.tailwindcss.com"></script>
<!-- Custom Mobile Styles -->
<style>
/* Mobile-first responsive adjustments */
@media (max-width: 768px) {
    /* Hide sidebar on mobile, show as drawer */
    [data-testid="stSidebar"] {
        position: fixed;
        z-index: 999;
        transform: translateX(-100%);
        transition: transform 0.3s ease;
        width: 85% !important;
        max-width: 320px;
    }
    [data-testid="stSidebar"][aria-expanded="true"] {
        transform: translateX(0);
    }
    /* Mobile header */
    .mobile-header {
        display: flex !important;
        position: sticky;
        top: 0;
        z-index: 998;
        background: white;
        padding: 0.75rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    /* Stack columns vertically on mobile */
    [class*="stColumns"] > div {
        margin-bottom: 0.5rem !important;
    }
    /* Larger touch targets */
    .stButton > button {
        padding: 0.75rem 1rem !important;
        min-height: 48px !important;
    }
    /* Larger input fields */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div {
        min-height: 48px !important;
        padding: 0.5rem !important;
    }
    /* Stat cards - larger on mobile */
    .stat-card {
        padding: 1rem !important;
    }
    /* Dataframe scrollable */
    [data-testid="stDataFrame"] {
        overflow-x: auto;
    }
    /* Bottom navigation */
    .bottom-nav {
        display: flex !important;
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
        z-index: 999;
        padding: 0.5rem;
        justify-content: space-around;
    }
    .bottom-nav-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 0.5rem;
        color: #666;
        text-decoration: none;
        font-size: 0.75rem;
    }
    .bottom-nav-item.active {
        color: #3b82f6;
    }
    /* Add padding for bottom nav */
    .main-content {
        padding-bottom: 80px !important;
    }
}
/* Desktop - hide mobile elements */
@media (min-width: 769px) {
    .mobile-header, .bottom-nav {
        display: none !important;
    }
    [data-testid="stSidebar"] {
        position: relative;
    }
}
/* Stat card styling */
.stat-card {
    background: white;
    border-radius: 0.75rem;
    padding: 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: transform 0.2s, box-shadow 0.2s;
}
.stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.stat-value {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1f2937;
}
.stat-label {
    font-size: 0.875rem;
    color: #6b7280;
    margin-top: 0.25rem;
}
.stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
}
/* Status badge styling */
.status-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.375rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.875rem;
    font-weight: 500;
}
.status-running {
    background: #dcfce7;
    color: #166534;
}
.status-idle {
    background: #f3f4f6;
    color: #4b5563;
}
.status-error {
    background: #fee2e2;
    color: #991b1b;
}
/* Card component */
.dashboard-card {
    background: white;
    border-radius: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    overflow: hidden;
}
.card-header {
    padding: 1rem 1.25rem;
    border-bottom: 1px solid #e5e7eb;
    font-weight: 600;
    color: #374151;
}
.card-body {
    padding: 1.25rem;
}
/* Responsive tabs */
.responsive-tabs {
    display: flex;
    gap: 0.5rem;
    overflow-x: auto;
    padding: 0.25rem;
    -webkit-overflow-scrolling: touch;
}
.tab-btn {
    padding: 0.5rem 1rem;
    border-radius: 0.5rem;
    font-weight: 500;
    white-space: nowrap;
    border: none;
    cursor: pointer;
    transition: all 0.2s;
}
.tab-btn.active {
    background: #3b82f6;
    color: white;
}
.tab-btn:not(.active) {
    background: #f3f4f6;
    color: #6b7280;
}
/* FlyonUI drawer toggle */
.drawer-toggle {
    display: none;
}
@media (max-width: 768px) {
    .drawer-toggle {
        display: block;
        position: fixed;
        top: 0.75rem;
        left: 0.75rem;
        z-index: 1000;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        padding: 0.5rem;
        cursor: pointer;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
}
</style>
""", unsafe_allow_html=True)

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

def get_time_info():
    """Get last updated time in local timezone and calculate next run."""
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
                time_remaining_text = "Overdue - run now!"
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
            df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        return df
    except sqlite3.OperationalError:
        return pd.DataFrame()

def load_status():
    """Fetches the live status of the scraper."""
    if not os.path.exists(DB_PATH):
        return "Waiting for scraper to initialize...", None
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT status, last_updated FROM scraper_status WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            status = row[0] if row[0] else "No status yet"
            last_updated = row[1]
            return status, last_updated
        else:
            return "No status record found", None
    except sqlite3.OperationalError:
        return "Database not ready", None
    except Exception as e:
        return f"Error: {str(e)}", None

def extract_coords(address):
    """Extract latitude and longitude from address string."""
    if not address or pd.isna(address):
        return None, None
    pattern = r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)"
    match = re.search(pattern, str(address))
    if match:
        try:
            lat = float(match.group(1))
            lon = float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
        except ValueError:
            pass
    return None, None

df = load_data()
status_text, last_updated = load_status()

scraper_running = status_text and (
    "Crawling" in status_text or 
    "Running" in status_text or
    "Scrolling" in status_text or
    "Extracting" in status_text or
    "Attempt" in status_text or
    "Job Started" in status_text
)
should_refresh = scraper_running

if should_refresh:
    count = st_autorefresh(interval=30000, limit=None, key="live_scraper_refresh")

# Mobile header with drawer toggle
st.markdown("""
<div class="mobile-header">
    <button class="drawer-toggle" onclick="document.querySelector('[data-testid=\\'stSidebar\\']').setAttribute('aria-expanded', 'true')">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
    </button>
    <span style="font-weight: 700; font-size: 1.125rem; margin-left: 0.5rem;">🏢 Business Leads</span>
</div>
""", unsafe_allow_html=True)

# Main content wrapper
st.markdown('<div class="main-content">', unsafe_allow_html=True)

st.title("🏢 Business Leads Dashboard")
st.markdown("📍 Analyze scraped business leads from Google Maps")

# --- SIDEBAR: Scraper Controls ---
with st.sidebar:
    st.header("🚀 Scraper Controls")
    
    # Status with FlyonUI styling
    if "Sleeping" in status_text or "Idle" in status_text or "Stopped" in status_text:
        st.markdown(f"""
        <div class="status-badge status-idle">
            <span style="margin-right: 0.5rem;">💤</span> {status_text}
        </div>
        """, unsafe_allow_html=True)
        is_running = False
    elif "Error" in status_text or "Failed" in status_text:
        st.markdown(f"""
        <div class="status-badge status-error">
            <span style="margin-right: 0.5rem;">❌</span> {status_text}
        </div>
        """, unsafe_allow_html=True)
        is_running = False
    else:
        st.markdown(f"""
        <div class="status-badge status-running">
            <span style="margin-right: 0.5rem;">🤖</span> {status_text}
        </div>
        """, unsafe_allow_html=True)
        is_running = True
    
    # Time info with FlyonUI cards
    last_updated_local, next_run_local, time_remaining_text = get_time_info()
    
    if last_updated_local:
        st.markdown(f"""
        <div class="dashboard-card" style="margin-top: 1rem;">
            <div class="card-body">
                <div style="font-size: 0.75rem; color: #6b7280; margin-bottom: 0.25rem;">📅 Last Updated</div>
                <div style="font-weight: 600; color: #1f2937;">{last_updated_local.strftime('%Y-%m-%d %H:%M')}</div>
                <div style="font-size: 0.75rem; color: #9ca3af;">UTC+5 (Your Time)</div>
            </div>
        </div>
        <div class="dashboard-card" style="margin-top: 0.5rem;">
            <div class="card-body">
                <div style="font-size: 0.75rem; color: #6b7280; margin-bottom: 0.25rem;">⏱️ Next Scheduled</div>
                <div style="font-weight: 600; color: #1f2937;">{next_run_local.strftime('%Y-%m-%d %H:%M')}</div>
            </div>
        </div>
        <div class="dashboard-card" style="margin-top: 0.5rem;">
            <div class="card-body">
                <div style="font-size: 0.75rem; color: #6b7280; margin-bottom: 0.25rem;">⏳ Time Remaining</div>
                <div style="font-weight: 700; color: #3b82f6; font-size: 1.25rem;">{time_remaining_text}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Action buttons with full width
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("▶️ Start", disabled=is_running, use_container_width=True):
            try:
                python_executable = sys.executable
                subprocess.Popen(
                    [python_executable, "scraper.py", "run"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                st.toast("Scraper started! 🚀", icon="🚀")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")
    with col_btn2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    st.markdown("---")
    st.header("🔍 Filters")
    
    # Filter logic
    locations = df['country'].dropna().unique().tolist() if 'country' in df.columns else []
    if locations:
        locations.insert(0, "All Locations")
        selected_location = st.selectbox("Country", locations)
    else:
        selected_location = "All Locations"
        
    queries = df['query'].dropna().unique().tolist() if 'query' in df.columns else []
    if queries:
        queries.insert(0, "All Queries")
        selected_query = st.selectbox("Category", queries)
    else:
        selected_query = "All Queries"
    
    search_name = st.text_input("🔎 Search Business", placeholder="Type name...")
    
    # Contact filters as expandable
    with st.expander("📱 Contact Filters"):
        has_phone_filter = st.radio("Phone", ["All", "Has Phone", "No Phone"], horizontal=True)
        has_email_filter = st.radio("Email", ["All", "Has Email", "No Email"], horizontal=True)
        has_website_filter = st.radio("Website", ["All", "Has Website", "No Website"], horizontal=True)
    
    st.metric("📊 Filtered Leads", len(df))

if df.empty:
    st.warning(f"No data found. Run `scraper.py` first.")
    st.stop()

# Extract coordinates
coords = df['address'].apply(extract_coords)
df['latitude'] = coords.apply(lambda x: x[0])
df['longitude'] = coords.apply(lambda x: x[1])

# ===== STATS ROW WITH FLYONUI CARDS =====
st.markdown("### 📊 Overview")

# Responsive stats grid
total_businesses = len(df)
businesses_with_phone = df[df['phone'].notna() & (df['phone'] != 'N/A') & (df['phone'] != '')].shape[0] if 'phone' in df.columns else 0
businesses_with_email = df[df['email'].notna() & (df['email'] != 'N/A') & (df['email'] != '')].shape[0] if 'email' in df.columns else 0
businesses_with_website = df[df['website'].notna() & (df['website'] != 'N/A') & (df['website'] != '')].shape[0] if 'website' in df.columns else 0

# Stats as HTML cards for better styling
st.markdown(f"""
<div class="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
    <div class="stat-card">
        <div class="stat-icon" style="background: #dbeafe; color: #2563eb;">📊</div>
        <div class="stat-value">{total_businesses}</div>
        <div class="stat-label">Total Leads</div>
    </div>
    <div class="stat-card">
        <div class="stat-icon" style="background: #dcfce7; color: #16a34a;">📱</div>
        <div class="stat-value">{businesses_with_phone}</div>
        <div class="stat-label">Has Phone</div>
    </div>
    <div class="stat-card">
        <div class="stat-icon" style="background: #fef3c7; color: #d97706;">📧</div>
        <div class="stat-value">{businesses_with_email}</div>
        <div class="stat-label">Has Email</div>
    </div>
    <div class="stat-card">
        <div class="stat-icon" style="background: #f3e8ff; color: #9333ea;">🌐</div>
        <div class="stat-value">{businesses_with_website}</div>
        <div class="stat-label">Has Website</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Category chips
if 'query' in df.columns:
    category_counts = df['query'].value_counts()
    chips_html = '<div class="flex flex-wrap gap-2 mt-4">'
    for cat, count in category_counts.items():
        chips_html += f'<span class="badge badge-primary badge-lg">{cat}: {count}</span>'
    chips_html += '</div>'
    st.markdown(chips_html, unsafe_allow_html=True)

# Apply filters
filtered_df = df.copy()
if selected_location != "All Locations" and 'country' in df.columns:
    filtered_df = filtered_df[filtered_df['country'] == selected_location]
if selected_query != "All Queries" and 'query' in df.columns:
    filtered_df = filtered_df[filtered_df['query'] == selected_query]
if search_name and 'name' in df.columns:
    filtered_df = filtered_df[filtered_df['name'].str.contains(search_name, case=False, na=False)]

if has_phone_filter == "Has Phone":
    filtered_df = filtered_df[filtered_df['phone'].notna() & (filtered_df['phone'] != 'N/A') & (filtered_df['phone'] != '')]
elif has_phone_filter == "No Phone":
    filtered_df = filtered_df[(filtered_df['phone'].isna()) | (filtered_df['phone'] == 'N/A') | (filtered_df['phone'] == '')]

if has_email_filter == "Has Email":
    filtered_df = filtered_df[filtered_df['email'].notna() & (filtered_df['email'] != 'N/A') & (filtered_df['email'] != '')]
elif has_email_filter == "No Email":
    filtered_df = filtered_df[(filtered_df['email'].isna()) | (filtered_df['email'] == 'N/A') | (filtered_df['email'] == '')]

if has_website_filter == "Has Website":
    filtered_df = filtered_df[filtered_df['website'].notna() & (filtered_df['website'] != 'N/A') & (filtered_df['website'] != '')]
elif has_website_filter == "No Website":
    filtered_df = filtered_df[(filtered_df['website'].isna()) | (filtered_df['website'] == 'N/A') | (filtered_df['website'] == '')]

# Tabs with icons
tab1, tab2, tab3 = st.tabs(["📋 Data", "📊 Analysis", "🗺️ Map"])

with tab1:
    display_cols = ['name', 'rating', 'category', 'address', 'phone', 'email', 'website', 'timestamp']
    actual_cols = [c for c in display_cols if c in filtered_df.columns]
    st.dataframe(filtered_df[actual_cols], use_container_width=True, hide_index=True)

with tab2:
    if 'category' in filtered_df.columns:
        counts = filtered_df['category'].value_counts().reset_index()
        counts.columns = ['Category', 'Count']
        st.bar_chart(counts, x='Category', y='Count', use_container_width=True)

with tab3:
    map_df = filtered_df.dropna(subset=['latitude', 'longitude'])
    if not map_df.empty:
        st.map(map_df, use_container_width=True)
        st.caption(f"📍 Showing {len(map_df)} locations")
    else:
        st.info("No valid coordinates found in data")

# Bottom navigation for mobile
st.markdown("""
<div class="bottom-nav">
    <a href="#" class="bottom-nav-item active">
        <span style="font-size: 1.5rem;">📋</span>
        <span>Data</span>
    </a>
    <a href="#" class="bottom-nav-item">
        <span style="font-size: 1.5rem;">📊</span>
        <span>Stats</span>
    </a>
    <a href="#" class="bottom-nav-item">
        <span style="font-size: 1.5rem;">🗺️</span>
        <span>Map</span>
    </a>
    <a href="#" class="bottom-nav-item">
        <span style="font-size: 1.5rem;">⚙️</span>
        <span>Settings</span>
    </a>
</div>
""", unsafe_allow_html=True)

# Close main content wrapper
st.markdown('</div>', unsafe_allow_html=True)
