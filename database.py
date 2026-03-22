"""
Supabase Database Module
"""
import os
from supabase import create_client, Client

# Supabase credentials
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://jkwbnpevkgjhlsttamxz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imprd2JucGV2a2dqaGxzdHRhbXh6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQyMDE3ODQsImV4cCI6MjA4OTc3Nzc4NH0.tc8kVPCBru8ghCLSQ6D_FDEC9H_45kpcNwAa2ja6-gg")

# Initialize client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_leads():
    """Fetch all leads from Supabase"""
    response = supabase.table("leads").select("*").order("timestamp", desc=True).execute()
    return response.data

def get_leads_by_name(name):
    """Get a lead by exact name"""
    response = supabase.table("leads").select("*").eq("name", name).execute()
    return response.data

def insert_lead(lead_data):
    """Insert a new lead"""
    response = supabase.table("leads").insert(lead_data).execute()
    return response.data

def update_lead(id, lead_data):
    """Update an existing lead"""
    response = supabase.table("leads").update(lead_data).eq("id", id).execute()
    return response.data

def upsert_lead(lead_data):
    """Insert or update a lead based on name"""
    # Check if exists
    existing = get_leads_by_name(lead_data.get("name"))
    if existing:
        # Update
        return update_lead(existing[0]["id"], lead_data)
    else:
        # Insert
        return insert_lead(lead_data)

def get_status():
    """Get scraper status"""
    response = supabase.table("scraper_status").select("*").eq("id", 1).execute()
    if response.data:
        return response.data[0]
    return None

def update_status(status_text):
    """Update scraper status"""
    response = supabase.table("scraper_status").upsert({
        "id": 1,
        "status": status_text,
        "last_updated": "now()"
    }).execute()
    return response.data

def get_lead_count():
    """Get total lead count"""
    response = supabase.table("leads").select("*", count="exact").execute()
    return response.count or 0

def get_time_info():
    """Get last updated time in local timezone and calculate next run."""
    try:
        status = get_status()
        if status and status.get('last_updated'):
            last_updated_str = status['last_updated']
            # Handle both string and datetime formats
            if isinstance(last_updated_str, str):
                last_updated = datetime.datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
            else:
                last_updated = last_updated_str
            
            # Get local timezone offset (UTC+5 for Tashkent)
            local_tz = datetime.timezone(datetime.timedelta(hours=5))
            
            # Convert to local time
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=datetime.timezone.utc)
            last_updated_local = last_updated.astimezone(local_tz)
            
            # Calculate next run (72 hours from last run)
            next_run = last_updated + datetime.timedelta(hours=72)
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=datetime.timezone.utc)
            next_run_local = next_run.astimezone(local_tz)
            
            # Calculate time remaining
            now = datetime.datetime.now(local_tz)
            time_remaining = next_run_local - now
            
            if time_remaining.total_seconds() < 0:
                time_remaining_text = "Overdue!"
            else:
                hours = int(time_remaining.total_seconds() // 3600)
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                time_remaining_text = f"{hours}h {minutes}m"
            
            return last_updated_local, next_run_local, time_remaining_text
    except Exception as e:
        print(f"Error getting time info: {e}")
    return None, None, None
