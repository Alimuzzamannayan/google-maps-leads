import streamlit as st
import sqlite3
import pandas as pd
import os
import re
import subprocess
import sys
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Business Leads Dashboard", page_icon="🏢", layout="wide")

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

def load_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH)
        # Query from the leads table
        df = pd.read_sql_query("SELECT * FROM leads", conn)
        conn.close()
        
        # Remove duplicates - keep the latest entry for each business name
        if not df.empty and 'name' in df.columns and 'timestamp' in df.columns:
            # Sort by timestamp descending and drop duplicates, keeping first (latest)
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df.sort_values('timestamp', ascending=False)
            df = df.drop_duplicates(subset=['name'], keep='first')
            # Convert timestamp back to string for display
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
        cursor.execute("SELECT status_text, last_updated FROM scraper_status WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0], row[1]
    except sqlite3.OperationalError:
        pass
    return "Unknown Status", None

def extract_coords(address):
    """Attempt to extract Decimal Degrees lat/long from address strings if present."""
    if not isinstance(address, str):
        return None, None
    # Look for common latlng patterns like 4.1755, 73.5093
    # Note: Scraped addresses from feed views rarely contain coords natively unless explicitly in the text
    # This regex looks for two numbers with decimals separated by a comma (with optional spaces)
    pattern = r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)"
    match = re.search(pattern, address)
    if match:
        try:
            lat = float(match.group(1))
            lon = float(match.group(2))
            # Basic validation for lat/lon bounds
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
        except ValueError:
            pass
    return None, None

df = load_data()
status_text, last_updated = load_status()

# Always enable auto-refresh when scraper is running (check for various status patterns)
scraper_running = status_text and (
    "Crawling" in status_text or 
    "Running" in status_text or
    "Scrolling" in status_text or
    "Extracting" in status_text or
    "Attempt" in status_text or
    "Job Started" in status_text
)

# Check if we should enable auto-refresh
should_refresh = scraper_running

if should_refresh:
    # Automatically refresh the page every 30 seconds to show live scraper updates
    count = st_autorefresh(interval=30000, limit=None, key="live_scraper_refresh")

st.title("🏢 Business Leads Dashboard")
st.markdown("Analyze scraped business leads extracted from Google Maps.")

# --- SIDEBAR: Scraper Controls ---
with st.sidebar:
    st.header("🚀 Scraper Controls")
    
    # Determine color based on status text
    if "Sleeping" in status_text or "Idle" in status_text or "Stopped" in status_text:
        st.info(f"**💤 Status:** {status_text}")
        is_running = False
    elif "Error" in status_text or "Failed" in status_text:
        st.error(f"**❌ Status:** {status_text}")
        is_running = False
    else:
        # Active crawling
        st.success(f"**🤖 Status:** {status_text}")
        is_running = True
    
    if last_updated:
        st.caption(f"*Last Updated: {last_updated}*")
    
    # Start/Stop Button
    if st.button("▶️ Start Scraper", disabled=is_running, use_container_width=True):
        try:
            # Launch scraper.py as a background process using the current virtual environment's python
            python_executable = sys.executable
            subprocess.Popen(
                [python_executable, "scraper.py", "run"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            st.toast("Scraper started in the background!", icon="🚀")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to start scraper: {e}")
    
    # Manual Refresh Button
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()
    
    st.markdown("---")
    st.header("🔍 Filter Data")
    
    # Filter logic for 'country' / Location
    locations = df['country'].dropna().unique().tolist() if 'country' in df.columns else []
    if locations:
        locations.insert(0, "All Locations")
        selected_location = st.selectbox("Select Country or Location", locations)
    else:
        selected_location = "All Locations"
        
    # Filter logic for 'query'
    queries = df['query'].dropna().unique().tolist() if 'query' in df.columns else []
    if queries:
        queries.insert(0, "All Queries")
        selected_query = st.selectbox("Select Query", queries)
    else:
        selected_query = "All Queries"
    
    search_name = st.text_input("Search Business Name", "")
    
    # Filter by phone/email availability
    st.markdown("#### 📱 Contact Filters")
    has_phone_filter = st.radio("Has Phone Number?", 
                               ["All", "Has Phone", "No Phone"], 
                               horizontal=True)
    has_email_filter = st.radio("Has Email?", 
                               ["All", "Has Email", "No Email"], 
                               horizontal=True)
    has_website_filter = st.radio("Has Website?", 
                               ["All", "Has Website", "No Website"], 
                               horizontal=True)
    
    st.markdown("---")
    st.metric("Filtered Leads Displayed", len(df) if df.empty else 0)

if df.empty:
    st.warning(f"No data found in `{DB_NAME}`. Run `scraper.py` first.")
    st.stop()

# Extract coordinates into new columns if they exist in the address
coords = df['address'].apply(extract_coords)
df['latitude'] = coords.apply(lambda x: x[0])
df['longitude'] = coords.apply(lambda x: x[1])

# ===== COMPACT COUNT DASHBOARD =====
# Row 1: Main metrics
row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
total_businesses = len(df)
row1_col1.metric("📊 Total Leads", total_businesses)

# Count businesses with phone numbers
if 'phone' in df.columns:
    businesses_with_phone = df[df['phone'].notna() & (df['phone'] != 'N/A') & (df['phone'] != '')].shape[0]
    row1_col2.metric("📱 Has Phone", businesses_with_phone)

# Count businesses with emails
if 'email' in df.columns:
    businesses_with_email = df[df['email'].notna() & (df['email'] != 'N/A') & (df['email'] != '')].shape[0]
    row1_col3.metric("📧 Has Email", businesses_with_email)

# Count businesses with websites
if 'website' in df.columns:
    businesses_with_website = df[df['website'].notna() & (df['website'] != 'N/A') & (df['website'] != '')].shape[0]
    row1_col4.metric("🌐 Has Website", businesses_with_website)

# Row 2: Counts by category
st.markdown("##### 📋 Leads by Category")
if 'query' in df.columns:
    category_counts = df['query'].value_counts()
    # Display as inline chips/tags
    cols = st.columns(len(category_counts))
    for idx, (cat, count) in enumerate(category_counts.items()):
        cols[idx].markdown(f"**{cat}:** {count}")

st.markdown("---)")

# Apply filters
filtered_df = df.copy()
if selected_location != "All Locations" and 'country' in df.columns:
    filtered_df = filtered_df[filtered_df['country'] == selected_location]
if selected_query != "All Queries" and 'query' in df.columns:
    filtered_df = filtered_df[filtered_df['query'] == selected_query]
if search_name and 'name' in df.columns:
    filtered_df = filtered_df[filtered_df['name'].str.contains(search_name, case=False, na=False)]

# Apply phone filter
if has_phone_filter == "Has Phone":
    filtered_df = filtered_df[filtered_df['phone'].notna() & (filtered_df['phone'] != 'N/A') & (filtered_df['phone'] != '')]
elif has_phone_filter == "No Phone":
    filtered_df = filtered_df[(filtered_df['phone'].isna()) | (filtered_df['phone'] == 'N/A') | (filtered_df['phone'] == '')]

# Apply email filter
if has_email_filter == "Has Email":
    filtered_df = filtered_df[filtered_df['email'].notna() & (filtered_df['email'] != 'N/A') & (filtered_df['email'] != '')]
elif has_email_filter == "No Email":
    filtered_df = filtered_df[(filtered_df['email'].isna()) | (filtered_df['email'] == 'N/A') | (filtered_df['email'] == '')]

# Apply website filter
if has_website_filter == "Has Website":
    filtered_df = filtered_df[filtered_df['website'].notna() & (filtered_df['website'] != 'N/A') & (filtered_df['website'] != '')]
elif has_website_filter == "No Website":
    filtered_df = filtered_df[(filtered_df['website'].isna()) | (filtered_df['website'] == 'N/A') | (filtered_df['website'] == '')]

# Update metric in sidebar
st.sidebar.metric("Filtered Leads Displayed", len(filtered_df))

tab1, tab2, tab3 = st.tabs(["📋 Data Table", "📊 Category Analysis", "🗺️ Map View"])

with tab1:
    # Display the searchable table - include email and website if available
    display_cols = ['name', 'rating', 'category', 'address', 'phone', 'email', 'website', 'timestamp']
    # Filter for only columns that actually exist in the dataframe
    actual_cols = [c for c in display_cols if c in filtered_df.columns]
    st.dataframe(filtered_df[actual_cols], width='stretch', hide_index=True)

with tab2:
    if 'category' in filtered_df.columns:
        counts = filtered_df['category'].value_counts().reset_index()
        counts.columns = ['Category', 'Count']
        st.bar_chart(counts, x='Category', y='Count', width='stretch')
        
with tab3:
    st.subheader("Geographic Distribution")
    
    # Filter rows that successfully got lat/lon extracted
    map_df = filtered_df.dropna(subset=['latitude', 'longitude'])
    
    if not map_df.empty:
        st.map(map_df, width='stretch')
        st.caption(f"Showing {len(map_df)} locations with valid coordinates on the map.")
    else:
        st.info(
            "📍 No valid Latitude/Longitude coordinates were found in the current address data. "
            "Coordinates must be present in the extracted address string (e.g., '4.1755, 73.5093') to be plotted here."
        )
