"""
Reporter module for sending email reports after each scraping job.
"""
import smtplib
import os
import sqlite3
import pandas as pd
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import hashlib
import json


def get_report_stats(db_path, previous_snapshot):
    """
    Get statistics about the current state of the database compared to previous snapshot.
    
    Args:
        db_path: Path to the SQLite database
        previous_snapshot: Dict of {name: row_hash} from previous run
    
    Returns:
        Dictionary containing all statistics
    """
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM leads", conn)
    conn.close()
    
    # Calculate hash for each row
    def hash_row(row):
        row_str = '|'.join([str(v) for v in row.values()])
        return hashlib.md5(row_str.encode()).hexdigest()
    
    # Get current hashes
    current_hashes = {}
    new_companies = []
    updated_companies = []
    
    for _, row in df.iterrows():
        row_hash = hash_row(row)
        current_hashes[row['name']] = row_hash
        
        if row['name'] not in previous_snapshot:
            new_companies.append(row['name'])
        elif previous_snapshot[row['name']] != row_hash:
            updated_companies.append(row['name'])
    
    # Get details for new and updated companies
    new_companies_details = df[df['name'].isin(new_companies)][['name', 'category', 'country', 'phone', 'email', 'website']].to_dict('records')
    updated_companies_details = df[df['name'].isin(updated_companies)][['name', 'category', 'country', 'phone', 'email', 'website']].to_dict('records')
    
    # Build stats
    stats = {
        'new_companies': new_companies,
        'new_companies_details': new_companies_details,
        'updated_companies': updated_companies,
        'updated_companies_details': updated_companies_details,
        'total_leads': len(df),
        'category_breakdown': df['category'].value_counts().to_dict() if 'category' in df.columns else {},
        'locations_breakdown': df['country'].value_counts().to_dict() if 'country' in df.columns else {},
        'companies_with_phone': len(df[(df['phone'].notna()) & (df['phone'] != 'N/A') & (df['phone'] != '')]),
        'companies_with_email': len(df[(df['email'].notna()) & (df['email'] != 'N/A') & (df['email'] != '')]),
        'companies_with_website': len(df[(df['website'].notna()) & (df['website'] != 'N/A') & (df['website'] != '')]),
    }
    
    return stats


def build_snapshot(db_path):
    """
    Build a snapshot of the current database state for comparison in future runs.
    
    Args:
        db_path: Path to the SQLite database
    
    Returns:
        Dict of {name: hash_of_all_fields}
    """
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM leads", conn)
    conn.close()
    
    # Calculate hash for each row
    def hash_row(row):
        row_str = '|'.join([str(v) for v in row.values()])
        return hashlib.md5(row_str.encode()).hexdigest()
    
    snapshot = {}
    for _, row in df.iterrows():
        snapshot[row['name']] = hash_row(row)
    
    return snapshot


def build_html_email(stats, errors):
    """
    Build an HTML email with the stats and errors.
    
    Args:
        stats: Dictionary containing all statistics
        errors: List of error strings
    
    Returns:
        HTML email string and subject line
    """
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate summary
    total_leads = stats.get('total_leads', 0)
    new_count = len(stats.get('new_companies', []))
    updated_count = len(stats.get('updated_companies', []))
    error_count = len(errors)
    
    # Subject
    subject = f"🗺️ Scraper Report — {new_count} New Leads Found [{now.strftime('%Y-%m-%d')}]"
    
    # Build HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background-color: #ffffff; }}
            .header {{ background: linear-gradient(135deg, #1a73e8, #4285f4); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
            .content {{ padding: 30px; }}
            .summary {{ display: flex; justify-content: space-around; margin-bottom: 30px; }}
            .summary-box {{ text-align: center; padding: 20px; background: #f8f9fa; border-radius: 8px; flex: 1; margin: 0 10px; }}
            .summary-box .number {{ font-size: 32px; font-weight: bold; color: #1a73e8; }}
            .summary-box .label {{ color: #666; font-size: 14px; }}
            .section {{ margin-bottom: 30px; }}
            .section h2 {{ color: #333; font-size: 18px; border-bottom: 2px solid #1a73e8; padding-bottom: 10px; margin-bottom: 15px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background-color: #f8f9fa; font-weight: 600; color: #333; }}
            .company-name {{ font-weight: 600; color: #1a73e8; }}
            .category-tag {{ background: #e8f0fe; color: #1a73e8; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
            .location-tag {{ background: #fce8e6; color: #c5221f; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
            .new-tag {{ background: #e6f4ea; color: #137333; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
            .updated-tag {{ background: #fef7e0; color: #b06000; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
            .error-box {{ background: #fce8e6; border-left: 4px solid #c5221f; padding: 15px; margin-top: 20px; }}
            .error-box p {{ margin: 5px 0; color: #c5221f; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 14px; }}
            .metric {{ display: inline-block; margin: 0 15px; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #1a73e8; }}
            .metric-label {{ font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🗺️ Google Maps Scraper — Run Report</h1>
                <p>Generated on {date_str}</p>
            </div>
            
            <div class="content">
                <!-- Summary Section -->
                <div class="summary">
                    <div class="summary-box">
                        <div class="number">{total_leads}</div>
                        <div class="label">Total Leads</div>
                    </div>
                    <div class="summary-box">
                        <div class="number" style="color: #137333;">{new_count}</div>
                        <div class="label">New Found</div>
                    </div>
                    <div class="summary-box">
                        <div class="number" style="color: #b06000;">{updated_count}</div>
                        <div class="label">Updated</div>
                    </div>
                    <div class="summary-box">
                        <div class="number" style="color: #c5221f;">{error_count}</div>
                        <div class="label">Errors</div>
                    </div>
                </div>
                
                <!-- Contact Info Summary -->
                <div class="section" style="text-align: center; margin-bottom: 30px;">
                    <div class="metric">
                        <div class="metric-value">{stats.get('companies_with_phone', 0)}</div>
                        <div class="metric-label">📱 With Phone</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{stats.get('companies_with_email', 0)}</div>
                        <div class="metric-label">📧 With Email</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{stats.get('companies_with_website', 0)}</div>
                        <div class="metric-label">🌐 With Website</div>
                    </div>
                </div>
    """
    
    # Add new companies section
    if new_companies_details:
        html += """
                <div class="section">
                    <h2>✨ New Companies Found</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Company</th>
                                <th>Category</th>
                                <th>Location</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        for company in new_companies_details[:20]:  # Limit to 20
            html += f"""
                            <tr>
                                <td class="company-name">{company.get('name', 'N/A')}</td>
                                <td><span class="category-tag">{company.get('category', 'N/A')}</span></td>
                                <td><span class="location-tag">{company.get('country', 'N/A')}</span></td>
                            </tr>
            """
        if len(new_companies_details) > 20:
            html += f"""
                            <tr>
                                <td colspan="3" style="text-align: center; color: #666;">... and {len(new_companies_details) - 20} more</td>
                            </tr>
            """
        html += """
                        </tbody>
                    </table>
                </div>
        """
    
    # Add updated companies section
    if updated_companies_details:
        html += """
                <div class="section">
                    <h2>🔄 Updated Companies</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Company</th>
                                <th>Category</th>
                                <th>Location</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        for company in updated_companies_details[:20]:  # Limit to 20
            html += f"""
                            <tr>
                                <td class="company-name">{company.get('name', 'N/A')}</td>
                                <td><span class="category-tag">{company.get('category', 'N/A')}</span></td>
                                <td><span class="location-tag">{company.get('country', 'N/A')}</span></td>
                            </tr>
            """
        if len(updated_companies_details) > 20:
            html += f"""
                            <tr>
                                <td colspan="3" style="text-align: center; color: #666;">... and {len(updated_companies_details) - 20} more</td>
                            </tr>
            """
        html += """
                        </tbody>
                    </table>
                </div>
        """
    
    # Add category breakdown
    if stats.get('category_breakdown'):
        html += """
                <div class="section">
                    <h2>📊 Category Breakdown</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Category</th>
                                <th>Count</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        for category, count in stats['category_breakdown'].items():
            html += f"""
                            <tr>
                                <td>{category}</td>
                                <td><strong>{count}</strong></td>
                            </tr>
            """
        html += """
                        </tbody>
                    </table>
                </div>
        """
    
    # Add errors section
    if errors:
        html += """
                <div class="section">
                    <h2>⚠️ Errors & Warnings</h2>
                    <div class="error-box">
        """
        for error in errors[:10]:  # Limit to 10 errors
            html += f"<p>• {error}</p>"
        if len(errors) > 10:
            html += f"<p>... and {len(errors) - 10} more errors</p>"
        html += """
                    </div>
                </div>
        """
    
    # Footer
    html += f"""
            </div>
            
            <div class="footer">
                <p>🔄 <strong>Next run scheduled in 72 hours</strong></p>
                <p>This is an automated report from your Google Maps Scraper</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html, subject


def send_report(stats, errors):
    """
    Send an email report with the stats and errors.
    
    Args:
        stats: Dictionary containing all statistics
        errors: List of error strings
    """
    try:
        # Get environment variables
        zoho_email = os.environ.get('ZOHO_EMAIL')
        zoho_password = os.environ.get('ZOHO_APP_PASSWORD')
        recipient = os.environ.get('REPORT_RECIPIENT')
        
        # Check if all required env vars are set
        if not all([zoho_email, zoho_password, recipient]):
            print("[REPORT ERROR] Missing environment variables. Please set ZOHO_EMAIL, ZOHO_APP_PASSWORD, and REPORT_RECIPIENT")
            return
        
        # Build the email
        html_content, subject = build_html_email(stats, errors)
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = zoho_email
        msg['To'] = recipient
        
        # Attach HTML
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send via Zoho SMTP
        with smtplib.SMTP('smtp.zoho.com', 587) as server:
            server.starttls()
            server.login(zoho_email, zoho_password)
            server.send_message(msg)
        
        print("[REPORT] Email sent successfully")
        
    except Exception as e:
        print(f"[REPORT ERROR] {str(e)}")
        # Don't crash the scraper - just log the error


# Test function
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "data.db"
    
    # Test getting stats
    try:
        stats = get_report_stats(db_path, {})
        print("Stats:", stats)
    except Exception as e:
        print(f"Error: {e}")
