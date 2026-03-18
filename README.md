# Google Maps Business Leads Scraper

A production-ready Python application that automatically scrapes business leads from Google Maps and presents them through an interactive Streamlit dashboard.

## Overview

This project is designed to collect, manage, and visualize business lead data from Google Maps. It uses Selenium for web scraping with undetected-chromedriver to minimize detection, and Streamlit for a modern, interactive dashboard interface.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Google Maps    │────▶│   Scraper.py    │────▶│    SQLite DB    │
│  (Data Source)  │     │  (Selenium)     │     │   (data.db)     │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │    app.py       │
                                                │  (Streamlit)    │
                                                └─────────────────┘
```

## Features

### Core Features

| Feature | Description |
|---------|-------------|
| **Automated Scraping** | Collects business data from Google Maps across multiple regions and categories |
| **Smart Deduplication** | Compares all business fields (name, rating, category, address, phone, email, website) to prevent duplicates |
| **Data Updates** | Automatically updates existing records when business information changes |
| **Scheduled Runs** | Configurable automatic scraping every 72 hours |
| **Live Dashboard** | Real-time Streamlit dashboard with auto-refresh |

### Data Extraction

- **Business Name**: Extracted from card headers
- **Rating**: Star ratings when available
- **Category**: Business type classification
- **Address**: Physical location
- **Phone**: Phone numbers (including Viber/WhatsApp detection)
- **Email**: Email addresses when visible
- **Website**: URLs when available on business cards

## Installation

### Prerequisites

- Python 3.11 or higher
- Google Chrome browser
- Windows/Linux/Mac

### Quick Start

```bash
# 1. Clone and navigate to project
cd google-map-company-data-scrapper

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# OR
source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the dashboard
streamlit run app.py
```

## Configuration

### settings.json

Customize regions and search categories:

```json
{
  "regions": [
    "Malé, Maldives",
    "Hulhumalé, Maldives", 
    "Addu City, Maldives"
  ],
  "search_queries": [
    "Cafe",
    "Restaurant",
    "Retail",
    "Super Shop",
    "Guest house",
    "Resort",
    "Parlour",
    "Saloon",
    "Clinic",
    "Pharmacy",
    "Hospital",
    "Diagnostic center"
  ]
}
```

### Proxy Configuration (Optional)

Edit `PROXY_POOL` in `scraper.py` for production use:

```python
PROXY_POOL = [
    {"server": "http://proxy1.example.com:8080", "username": "user1", "password": "pass1"},
]
```

## Usage

### Dashboard

```bash
streamlit run app.py
```

Access at: **http://localhost:8501**

### Scraper

**Start scheduler only (recommended):**
```bash
python scraper.py
```

**Run immediately + scheduler:**
```bash
python scraper.py run
```

### Workflow

1. **Start Dashboard**: `streamlit run app.py`
2. **Start Scraper**: `python scraper.py run`
3. **Monitor**: Watch live data collection in the dashboard
4. **Schedule**: Scraper runs automatically every 72 hours

## Database Schema

```sql
CREATE TABLE leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    rating TEXT,
    category TEXT,
    address TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    country TEXT,
    query TEXT,
    timestamp TEXT
);

CREATE TABLE scraper_status (
    id INTEGER PRIMARY KEY,
    status_text TEXT,
    last_updated TEXT
);
```

## Key Components

### scraper.py

| Function | Purpose |
|----------|---------|
| `init_db()` | Initialize SQLite database with schema |
| `_make_driver()` | Create Chrome driver with anti-detection |
| `_scroll_feed()` | Load all results by scrolling |
| `_extract_all_cards()` | Extract business data from cards |
| `scrape_location()` | Main scraping logic with retry |
| `run_scraper_job()` | Orchestrates full scraping job |

### app.py

| Function | Purpose |
|----------|---------|
| `load_data()` | Load and deduplicate leads |
| `load_status()` | Get scraper status |
| `extract_coords()` | Parse coordinates from addresses |

## Dashboard Features

### Metrics
- Total Leads count
- Businesses with phone numbers
- Businesses with email addresses
- Businesses with websites
- Unique locations

### Filters
- By region/country
- By business category
- By name search
- Phone availability
- Email availability
- Website availability

### Tabs
1. **Data Table**: Full leads view with all fields
2. **Category Analysis**: Bar chart of business types
3. **Map View**: Geographic distribution (if coordinates in address)

## Deduplication Logic

The scraper implements intelligent deduplication:

```
For each scraped business:
├── Is name new? → Insert as new record
└── Name exists? → Compare ALL fields:
    ├── All fields same → Skip (no duplicate)
    └── Any field changed → Update existing record
```

The dashboard also auto-deduplicates on load, keeping the latest entry per business name.

## Important Notes

### Google Maps Limitations

- Phone/Email/Websites are NOT always visible on search result cards
- This data appears when clicking on a business details page
- The scraper attempts to extract this data through multiple methods:
  1. Direct selectors on cards
  2. Click-to-expand on business cards
  3. Pattern matching in card text

### Anti-Detection

- Uses `undetected-chromedriver` to avoid bot detection
- Implements random delays between requests
- Automatic retry with backoff on failures
- Proxy support for production deployments

## Troubleshooting

### Chrome Driver Issues
```bash
pip uninstall undetected-chromedriver
pip install undetected-chromedriver
```

### Reset Database
```bash
del data.db
python scraper.py run
```

### View Logs
Check terminal output for:
- `[STATUS]` - Scraper status messages
- `[Attempt X/Y]` - Retry attempts
- `Skipped X duplicates` - Duplicate prevention
- `Updated X existing records` - Data updates

## Project Structure

```
google-map-company-data-scrapper/
├── app.py                  # Streamlit dashboard
├── scraper.py              # Google Maps scraper
├── settings.json           # Configuration
├── requirements.txt        # Python dependencies
├── README.md              # Documentation
└── data.db               # SQLite database (auto-created)
```

## Dependencies

```
streamlit
streamlit-autorefresh
pandas
selenium
undetected-chromedriver
schedule
```

## License

MIT License

## Contributing

Contributions welcome! Please submit pull requests or open issues for bugs and feature requests.
