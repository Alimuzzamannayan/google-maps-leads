"""
Business Leads Dashboard - NiceGUI Version
Deployable to Vercel with Supabase database
"""
import os
from nicegui import app, ui
from database import get_leads, get_status, get_time_info
import pandas as pd
import re

# Page config
ui.page_title("Business Leads Dashboard")

def extract_coords(address):
    """Extract lat/lon from address string"""
    if not address: return None, None
    pattern = r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)"
    match = re.search(pattern, str(address))
    if match:
        try:
            lat, lon = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180: return lat, lon
        except: pass
    return None, None

def load_data():
    """Load leads from Supabase"""
    try:
        leads = get_leads()
        if leads:
            df = pd.DataFrame(leads)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
                df = df.sort_values('timestamp', ascending=False)
                df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
            return df
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

def load_status():
    """Load scraper status"""
    try:
        status = get_status()
        if status:
            return status.get('status', 'No status'), status.get('last_updated')
        return "No record", None
    except Exception:
        return "Connecting...", None

# Global state
df = load_data()
status_text, _ = load_status()

@ui.page('/')
def main_page():
    """Main dashboard page"""
    
    # Header
    with ui.header(elevated=True).classes('items-center justify-between bg-white'):
        ui.label('🏢 Business Leads').classes('text-xl font-bold')
        ui.label('📍 Google Maps • Maldives').classes('text-gray-500')
    
    # Main content
    with ui.column().classes('w-full max-w-7xl mx-auto p-4 gap-4'):
        
        # Status card
        with ui.card().classes('w-full'):
            with ui.row().classes('items-center justify-between w-full'):
                with ui.column():
                    ui.label('🚀 Scraper Status').classes('text-lg font-bold')
                    status_color = 'text-green-600' if 'Running' in status_text or 'Crawling' in status_text else 'text-gray-500'
                    ui.label(status_text).classes(f'{status_color} font-medium')
                with ui.column():
                    # Time info
                    lu, nr, tr = get_time_info()
                    if lu:
                        ui.label(f'Last: {lu.strftime("%d %b %H:%M")}').classes('text-sm text-gray-500')
                        ui.label(f'Next: {nr.strftime("%d %b %H:%M")}').classes('text-sm text-gray-500')
                        ui.label(f'⏱️ {tr}').classes('text-blue-600 font-bold')
        
        # Stats row
        total = len(df) if not df.empty else 0
        with_phone = len(df[df['phone'].notna() & (df['phone'] != 'N/A') & (df['phone'] != '')]) if not df.empty and 'phone' in df.columns else 0
        with_email = len(df[df['email'].notna() & (df['email'] != 'N/A') & (df['email'] != '')]) if not df.empty and 'email' in df.columns else 0
        with_web = len(df[df['website'].notna() & (df['website'] != 'N/A') & (df['website'] != '')]) if not df.empty and 'website' in df.columns else 0
        
        # Stats cards
        with ui.row().classes('w-full gap-4'):
            with ui.card().classes('flex-1 p-4 text-center'):
                ui.label('📊').classes('text-2xl')
                ui.label(str(total)).classes('text-3xl font-bold text-blue-600')
                ui.label('Total').classes('text-xs text-gray-500')
            
            with ui.card().classes('flex-1 p-4 text-center'):
                ui.label('📱').classes('text-2xl')
                ui.label(str(with_phone)).classes('text-3xl font-bold text-green-600')
                ui.label('Phone').classes('text-xs text-gray-500')
            
            with ui.card().classes('flex-1 p-4 text-center'):
                ui.label('📧').classes('text-2xl')
                ui.label(str(with_email)).classes('text-3xl font-bold text-yellow-600')
                ui.label('Email').classes('text-xs text-gray-500')
            
            with ui.card().classes('flex-1 p-4 text-center'):
                ui.label('🌐').classes('text-2xl')
                ui.label(str(with_web)).classes('text-3xl font-bold text-purple-600')
                ui.label('Website').classes('text-xs text-gray-500')
        
        # Category tags
        if not df.empty and 'query' in df.columns:
            tags = df['query'].value_counts().head(6)
            with ui.row().classes('w-full flex-wrap gap-2'):
                colors = ['bg-blue-100 text-blue-700', 'bg-green-100 text-green-700', 'bg-yellow-100 text-yellow-700', 'bg-purple-100 text-purple-700']
                for i, (cat, cnt) in enumerate(tags.items()):
                    ui.badge(f'{cat}: {cnt}').classes(colors[i % 4])
        
        # Filters
        with ui.card().classes('w-full'):
            ui.label('🔍 Filters').classes('text-lg font-bold')
            with ui.row().classes('w-full gap-4'):
                locations = sorted(df['country'].dropna().unique().tolist()) if not df.empty and 'country' in df.columns else []
                if locations: locations.insert(0, "All")
                else: locations = ["All"]
                
                queries = sorted(df['query'].dropna().unique().tolist()) if not df.empty and 'query' in df.columns else []
                if queries: queries.insert(0, "All")
                else: queries = ["All"]
                
                location_select = ui.select('Country', options=locations, value='All').classes('w-40')
                query_select = ui.select('Category', options=queries, value='All').classes('w-40')
                search_input = ui.input('Search', placeholder='Business name...').classes('w-48')
        
        # Data table
        with ui.card().classes('w-full'):
            ui.label('📋 Leads Data').classes('text-lg font-bold')
            
            # Apply filters
            fdf = df.copy()
            if location_select.value != 'All' and 'country' in fdf.columns:
                fdf = fdf[fdf['country'] == location_select.value]
            if query_select.value != 'All' and 'query' in fdf.columns:
                fdf = fdf[fdf['query'] == query_select.value]
            if search_input.value and 'name' in fdf.columns:
                fdf = fdf[fdf['name'].str.contains(search_input.value, case=False, na=False)]
            
            # Display columns
            display_cols = [c for c in ['name', 'rating', 'category', 'address', 'phone', 'email', 'website', 'timestamp'] if c in fdf.columns]
            
            # Create table
            if not fdf.empty:
                columns = [{'name': c, 'label': c.upper(), 'field': c, 'align': 'left'} for c in display_cols]
                rows = fdf[display_cols].to_dict('records')
                ui.table(columns=columns, rows=rows).classes('w-full')
            else:
                ui.label('No data found').classes('text-gray-500')
            
            ui.label(f'Showing {len(fdf)} leads').classes('text-sm text-gray-500')

# Run the app
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), reload=False)
