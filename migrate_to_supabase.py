import sqlite3
import database

def migrate():
    print("Starting bulk migration from data.db to Supabase...")
    try:
        conn = sqlite3.connect('data.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM leads')
        rows = cursor.fetchall()
        
        if not rows:
            print("No leads found in data.db")
            return
            
        leads_list = []
        for row in rows:
            ld = dict(row)
            if 'id' in ld:
                del ld['id'] # Supabase creates its own ID
                
            if 'email' not in ld: ld['email'] = 'N/A'
            if 'website' not in ld: ld['website'] = 'N/A'
            
            leads_list.append(ld)
            
        # Insert in chunks of 50 to avoid timeout/size limits
        chunk_size = 50
        for i in range(0, len(leads_list), chunk_size):
            chunk = leads_list[i:i+chunk_size]
            try:
                database.supabase.table("leads").insert(chunk).execute()
                print(f"Inserted chunk {i//chunk_size + 1}/{len(leads_list)//chunk_size + 1} ({len(chunk)} records)")
            except Exception as e:
                print(f"Chunk error at {i}: {e}")
                
        print(f"Successfully migrated {len(leads_list)} leads to Supabase.")
        
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    migrate()
