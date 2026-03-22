import sqlite3
import json
import os
import time
import random
import re
import schedule
from datetime import datetime
from urllib.parse import quote_plus

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

DB_NAME = "data.db"
SETTINGS_FILE = "settings.json"

# Use Supabase if environment variable is set
USE_SUPABASE = os.environ.get("USE_SUPABASE", "true").lower() == "true"

if USE_SUPABASE:
    try:
        from database import supabase, get_leads_by_name, upsert_lead, update_status as db_update_status, get_status as db_get_status
        print("[INFO] Using Supabase for data storage")
    except Exception as e:
        print(f"[WARN] Could not load Supabase: {e}")
        USE_SUPABASE = False

# ── Proxy Pool ────────────────────────────────────────────────────────────────
# Add real proxy credentials. Leave empty [] to run without proxy.
PROXY_POOL = [
    # {"server": "http://proxy1.example.com:8080", "username": "user1", "password": "pass1"},
]

def get_random_proxy():
    if not PROXY_POOL:
        return None
    return random.choice(PROXY_POOL)

# ── Database ──────────────────────────────────────────────────────────────────

def init_db():
    if USE_SUPABASE:
        # Supabase doesn't need local initialization
        return None
    
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS leads (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        name      TEXT, rating TEXT, category TEXT,
        address   TEXT, phone TEXT, email TEXT,
        website   TEXT,
        country   TEXT, query TEXT, timestamp TEXT
    )''')
    # Add email column if it doesn't exist (for existing databases)
    try:
        conn.execute('ALTER TABLE leads ADD COLUMN email TEXT')
    except:
        pass  # Column already exists
    # Add website column if it doesn't exist
    try:
        conn.execute('ALTER TABLE leads ADD COLUMN website TEXT')
    except:
        pass  # Column already exists
    conn.execute('''CREATE TABLE IF NOT EXISTS scraper_status (
        id INTEGER PRIMARY KEY, status_text TEXT, last_updated TEXT
    )''')
    conn.execute(
        'INSERT OR IGNORE INTO scraper_status (id, status_text, last_updated) VALUES (1,"Idle",?)',
        (datetime.now().isoformat(),)
    )
    conn.commit()
    return conn


def update_status(msg, conn=None):
    if USE_SUPABASE:
        db_update_status(msg)
        print(f"[STATUS] {msg}")
        return
    
    close = False
    if conn is None:
        conn = sqlite3.connect(DB_NAME)
        close = True
    conn.execute(
        'UPDATE scraper_status SET status_text=?, last_updated=? WHERE id=1',
        (msg, datetime.now().isoformat())
    )
    conn.commit()
    if close:
        conn.close()
    print(f"[STATUS] {msg}")

# ── Driver ────────────────────────────────────────────────────────────────────

def _make_driver(proxy=None):
    opts = uc.ChromeOptions()
    opts.add_argument("--window-size=1280,1000")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--lang=en-US")
    opts.add_argument("--disable-infobars")
    # Move to visible area but try to stay out of the way
    opts.add_argument("--window-position=0,0")
    if proxy:
        opts.add_argument(f"--proxy-server={proxy['server']}")
        print(f"  Using proxy: {proxy['server']}")
    driver = uc.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    # Make the driver less detectable by executing CDP commands
    try:
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
    except:
        pass
    return driver


def _is_blocked(driver) -> bool:
    signals = ["detected unusual traffic", "captcha", "before you continue",
               "our systems have detected"]
    try:
        text = (driver.title + driver.find_element(By.TAG_NAME, "body").text).lower()
        return any(s in text for s in signals)
    except Exception:
        return False


def _scroll_feed(driver, max_scrolls=25):
    """Scrolls the result sidebar until all cards are loaded."""
    print("  Scrolling feed...")
    try:
        feed = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']"))
        )
    except TimeoutException:
        print("  Could not find feed for scrolling.")
        return
    prev = 0
    stale = 0
    for _ in range(max_scrolls):
        # Count by name elements (known working selector)
        names = driver.find_elements(By.CSS_SELECTOR, ".qBF1Pd, .fontHeadlineSmall")
        cur = len(names)
        if cur == prev:
            stale += 1
            if stale >= 3:
                print(f"  End of feed ({cur} items).")
                break
        else:
            stale = 0
        prev = cur
        driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", feed)
        time.sleep(2)

# ── Data extraction ───────────────────────────────────────────────────────────

def _extract_name(card):
    """Try multiple selectors to find the business name within a card."""
    for sel in [".qBF1Pd", ".fontHeadlineSmall", "div.NrDZNb"]:
        try:
            el = card.find_element(By.CSS_SELECTOR, sel)
            t = el.text.strip()
            if t:
                return t
        except NoSuchElementException:
            continue
    return None

def _extract_all_cards(driver):
    """
    Finds all cards using the role='article' selector and extracts details.
    """
    cards = driver.find_elements(By.CSS_SELECTOR, "div[role='article'], .Nv2PK")
    print(f"  Container cards found: {len(cards)}")
    
    results = []
    for card in cards:
        try:
            # Name
            name = _extract_name(card)
            if not name:
                continue

            # Rating
            rating = "N/A"
            for sel in ["span[aria-label*='stars']", "span[role='img']", ".MW4etd"]:
                try:
                    rel = card.find_element(By.CSS_SELECTOR, sel)
                    aria = rel.get_attribute("aria-label") or ""
                    if "star" in aria.lower():
                        rating = aria.split()[0]
                        break
                    t = rel.text.strip()
                    if t:
                        rating = t
                        break
                except NoSuchElementException:
                    continue

            # Category
            category = "N/A"
            try:
                category = driver.execute_script("""
                    var card = arguments[0];
                    var spans = card.querySelectorAll('div.W4Efsd > span, span.W4Efsd');
                    for (var s of spans) {
                        var t = (s.innerText||'').replace('\\u00b7','').trim();
                        if (t && t.length > 2 && !t.includes('(') && !/^\\d/.test(t)) return t;
                    }
                    return 'N/A';
                """, card) or "N/A"
            except Exception:
                pass

            # Address
            address = "N/A"
            try:
                addr_el = card.find_element(By.CSS_SELECTOR, "button[data-item-id*='address']")
                address = addr_el.text.strip() or "N/A"
            except NoSuchElementException:
                try:
                    lines = card.text.split("\n")
                    kws = ["St","Rd","Ave","Road","Building","Magu","Floor","Block","Lane"]
                    for line in lines:
                        if any(k in line for k in kws):
                            address = line.strip()
                            break
                except Exception:
                    pass

            # Phone (including Viber, WhatsApp) - try to extract from card without clicking
            phone = "N/A"
            email = "N/A"
            website = "N/A"
            
            # First try to find phone directly on the card (no clicking to avoid detection)
            try:
                for sel in ["button[data-item-id*='phone']", "a[data-item-id*='phone']", 
                            "div[data-item-id*='phone']", "span[data-item-id*='phone']"]:
                    try:
                        ph_el = card.find_element(By.CSS_SELECTOR, sel)
                        phone = ph_el.text.strip()
                        if phone:
                            aria_label = ph_el.get_attribute('aria-label') or ""
                            if 'viber' in aria_label.lower():
                                phone = f"Viber: {phone}"
                            elif 'whatsapp' in aria_label.lower():
                                phone = f"WhatsApp: {phone}"
                            break
                    except NoSuchElementException:
                        continue
            except Exception:
                pass
            
            # Try to extract phone from card text using regex patterns
            if phone == "N/A":
                try:
                    card_text = card.text
                    # Look for phone patterns in text
                    phone_patterns = [
                        r'\+960\s?\d{4,}',  # Maldives format +960 xxx
                        r'\+960\d{4,}',
                        r'\b\d{3,4}[-.]?\d{3,4}\b',  # General phone format
                        r'\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}',
                    ]
                    for pattern in phone_patterns:
                        phone_match = re.search(pattern, card_text)
                        if phone_match:
                            phone = phone_match.group(0)
                            break
                except Exception:
                    pass
            
            # Try to find email directly on the card
            if email == "N/A":
                try:
                    for sel in ["a[href^='mailto:']", "button[data-item-id*='email']", 
                                "a[data-item-id*='email']", "div[data-item-id*='email']"]:
                        try:
                            email_el = card.find_element(By.CSS_SELECTOR, sel)
                            email = email_el.get_attribute('href') or email_el.text.strip()
                            if email and 'mailto:' in email:
                                email = email.replace('mailto:', '')
                            if email:
                                break
                        except NoSuchElementException:
                            continue
                except Exception:
                    pass
            
            # Try to extract email from card text as fallback
            if email == "N/A":
                try:
                    card_text = card.text
                    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                    email_match = re.search(email_pattern, card_text)
                    if email_match:
                        email = email_match.group(0)
                except Exception:
                    pass
            
            # Try to find website on the card (click to expand if needed)
            try:
                # First try direct selectors
                for sel in ["a[data-item-id*='website']", "button[data-item-id*='website']",
                            "div[data-item-id*='website']", "a[aria-label*='Website']"]:
                    try:
                        web_el = card.find_element(By.CSS_SELECTOR, sel)
                        website = web_el.get_attribute('href') or web_el.text.strip()
                        if website and 'http' in website.lower():
                            break
                        elif website and '.' in website and not website.startswith('http'):
                            website = 'https://' + website
                            break
                    except NoSuchElementException:
                        continue
                
                # If not found, try clicking on the card to expand it
                if website == "N/A":
                    try:
                        # Click on the name area to expand the card
                        name_el = card.find_element(By.CSS_SELECTOR, ".qBF1Pd, .fontHeadlineSmall, div.NrDZNb")
                        driver.execute_script("arguments[0].click();", name_el)
                        time.sleep(1)  # Wait for expansion
                        
                        # Look for website after expansion
                        for sel in ["a[data-item-id*='website']", "a.managed-link", 
                                    "div[data-item-id*='authority'] a"]:
                            try:
                                web_el = card.find_element(By.CSS_SELECTOR, sel)
                                href = web_el.get_attribute('href')
                                if href and ('http' in href or 'www' in href):
                                    website = href
                                    break
                            except NoSuchElementException:
                                continue
                    except Exception:
                        pass
            except Exception:
                pass
            
            # Try to find website in the card's links
            if website == "N/A":
                try:
                    links = card.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        href = link.get_attribute('href') or ""
                        text = link.text.strip()
                        # Check if this looks like a website
                        if 'website' in (href + text).lower() or ('.' in text and 'http' not in text and len(text) < 50):
                            if href and 'http' in href:
                                website = href
                                break
                            elif text and '.' in text:
                                website = 'https://' + text if not text.startswith('http') else text
                                break
                except Exception:
                    pass
            
            # Try to extract website from card text (looking for domain patterns)
            if website == "N/A":
                try:
                    card_text = card.text
                    # More robust website pattern
                    website_patterns = [
                        r'(https?://[\w.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)',
                        r'(?:www\.)([a-zA-Z0-9-]+\.[a-zA-Z]{2,})(?:/[^\s]*)?',
                    ]
                    for pattern in website_patterns:
                        web_match = re.search(pattern, card_text)
                        if web_match:
                            website = web_match.group(1) if 'http' not in web_match.group(1) else web_match.group(1)
                            if not website.startswith('http'):
                                website = 'https://' + website
                            break
                except Exception:
                    pass

            results.append({
                "name": name, "rating": rating,
                "category": category, "address": address,
                "phone": phone, "email": email, "website": website
            })

        except Exception as e:
            print(f"  Card extraction error: {e}")
            continue

    return results

# ── Main scraper ──────────────────────────────────────────────────────────────

def scrape_location(country_or_location, search_query, conn):
    MAX_RETRIES = 5
    combined = f"{search_query} in {country_or_location}"
    url = f"https://www.google.com/maps/search/{quote_plus(combined)}"
    print(f"\n{'='*60}\nQuery : {combined}\nURL   : {url}\n{'='*60}")
    update_status(f"Crawling: {combined}...", conn)

    # Load existing records from database to compare and avoid duplicates
    cursor = conn.cursor()
    cursor.execute("SELECT name, rating, category, address, phone, email, website FROM leads")
    existing_records = {}  # Dict to store name -> full record details
    for row in cursor.fetchall():
        existing_records[row[0]] = {
            'rating': row[1],
            'category': row[2],
            'address': row[3],
            'phone': row[4],
            'email': row[5],
            'website': row[6] if len(row) > 6 else 'N/A'
        }
    saved_names = set(existing_records.keys())  # Track names to avoid duplicates within this run
    print(f"  Existing leads in DB: {len(existing_records)}")

    for attempt in range(1, MAX_RETRIES + 1):
        proxy = get_random_proxy()
        print(f"\n[Attempt {attempt}/{MAX_RETRIES}]")
        update_status(f"Attempt {attempt}/{MAX_RETRIES} - {combined}", conn)
        driver = None

        try:
            driver = _make_driver(proxy)
            driver.get(url)
            time.sleep(random.uniform(3, 5))

            if _is_blocked(driver):
                raise RuntimeError("Google block detected. Switching proxy...")

            # Wait for feed
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']"))
                )
            except TimeoutException:
                driver.save_screenshot("blocked_screenshot.png")
                raise RuntimeError("Feed not found after 20s.")

            # Scroll to load all cards
            update_status(f"Scrolling - {combined} (attempt {attempt})", conn)
            _scroll_feed(driver)
            time.sleep(1)

            # Extract all cards
            update_status(f"Extracting - {combined}", conn)
            cards = _extract_all_cards(driver)
            print(f"  Extracted cards: {len(cards)}")

            if not cards:
                raise RuntimeError("No cards extracted after scroll - possible block or selector change.")

            # Save new ones
            new_count = 0
            skipped_count = 0
            updated_count = 0
            for row in cards:
                # Check if name already exists in saved_names (from this run)
                if row["name"] in saved_names:
                    # Check if data has been updated - compare with existing record in DB
                    if row["name"] in existing_records:
                        existing = existing_records[row["name"]]
                        # Compare all fields
                        data_changed = (
                            row["rating"] != existing.get('rating', 'N/A') or
                            row["category"] != existing.get('category', 'N/A') or
                            row["address"] != existing.get('address', 'N/A') or
                            row["phone"] != existing.get('phone', 'N/A') or
                            row["email"] != existing.get('email', 'N/A') or
                            row.get("website", "N/A") != existing.get('website', 'N/A')
                        )
                        if data_changed:
                            # Update existing record with new information
                            conn.execute(
                                '''UPDATE leads SET 
                                   rating=?, category=?, address=?, phone=?, email=?, 
                                   website=?, timestamp=? WHERE name=?''',
                                (row["rating"], row["category"], row["address"],
                                 row["phone"], row["email"], row.get("website", "N/A"),
                                 datetime.now().isoformat(), row["name"])
                            )
                            # Update our local cache
                            existing_records[row["name"]] = {
                                'rating': row["rating"],
                                'category': row["category"],
                                'address': row["address"],
                                'phone': row["phone"],
                                'email': row["email"],
                                'website': row.get("website", "N/A")
                            }
                            updated_count += 1
                        else:
                            # No data change - skip saving
                            skipped_count += 1
                    else:
                        # Name was already added in this run
                        skipped_count += 1
                    continue
                
                # New name - add to saved_names and insert into DB
                saved_names.add(row["name"])
                # Also add to existing_records for comparison in this run
                existing_records[row["name"]] = {
                    'rating': row["rating"],
                    'category': row["category"],
                    'address': row["address"],
                    'phone': row["phone"],
                    'email': row.get("email", "N/A"),
                    'website': row.get("website", "N/A")
                }
                conn.execute(
                    '''INSERT INTO leads
                       (name,rating,category,address,phone,email,website,country,query,timestamp)
                       VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (row["name"], row["rating"], row["category"], row["address"],
                     row["phone"], row.get("email", "N/A"), row.get("website", "N/A"),
                     country_or_location, search_query,
                     datetime.now().isoformat())
                )
                new_count += 1
                if new_count % 10 == 0:
                    conn.commit()
                    update_status(f"Crawling: {combined} - {new_count} leads saved", conn)

            conn.commit()
            if skipped_count > 0:
                print(f"  Skipped {skipped_count} duplicates (no changes)")
            if updated_count > 0:
                print(f"  Updated {updated_count} existing records")
            done = f"Done: {new_count} new, {updated_count} updated - {combined}"
            print(f"  [OK] {done}")
            update_status(done, conn)
            return list(saved_names)

        except RuntimeError as err:
            print(f"  [X] {err}")
            update_status(f"Retry {attempt}/{MAX_RETRIES} - {err}", conn)

        except Exception as err:
            print(f"  [X] Critical error: {err}")
            update_status(f"Error attempt {attempt}: {err}", conn)

        finally:
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass

        if attempt < MAX_RETRIES:
            backoff = random.uniform(5, 15)
            print(f"  Waiting {backoff:.1f}s before retry...")
            time.sleep(backoff)

    msg = f"All {MAX_RETRIES} retries failed for '{combined}'."
    print(f"  WARNING: {msg}")
    update_status(msg, conn)
    conn.commit()
    return []

# ── Scheduler ─────────────────────────────────────────────────────────────────

def run_scraper_job():
    print("\n" + "="*60 + "\nSTARTING SCRAPER JOB\n" + "="*60)
    update_status("Job Started. Initializing...")

    if not os.path.exists(SETTINGS_FILE):
        msg = f"{SETTINGS_FILE} not found."
        print(msg); update_status(msg); return

    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        settings = json.load(f)

    regions = settings.get("regions", [])
    queries  = settings.get("search_queries", [])
    conn = init_db()
    total = 0

    for region in regions:
        for query in queries:
            data = scrape_location(region, query, conn)
            total += len(data)
            time.sleep(random.uniform(3, 7))

    conn.close()
    finish = f"Job Complete. Total leads: {total}. Next run in 3 hours."
    print(f"\n{finish}")
    update_status(finish)


if __name__ == "__main__":
    import sys
    init_db()
    
    # Check if 'run' argument is passed to run immediately
    run_immediately = len(sys.argv) > 1 and sys.argv[1].lower() == 'run'
    
    if run_immediately:
        print("Running scraper job immediately...")
        run_scraper_job()
    else:
        print("Starting scheduler only. Will run every 72 hours.")
        print("To run immediately: python scraper.py run")
    
    # Set up scheduled runs every 72 hours
    schedule.every(72).hours.do(run_scraper_job)
    update_status("Scheduler active. Will run every 72 hours.")
    print("\nScheduler active. Running every 72 hours.")
    print("Manual trigger: python scraper.py run")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        update_status("Scraper stopped by user.")
        print("Stopped.")
