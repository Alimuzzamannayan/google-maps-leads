import time
import json
from urllib.parse import quote_plus
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def run_diagnostic():
    url = f"https://www.google.com/maps/search/{quote_plus('software companies in Male, Maldives')}"
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,1000")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=en-US")
    
    results = {"url": url, "steps": []}
    driver = uc.Chrome(options=options)
    
    try:
        driver.get(url)
        results["steps"].append("Navigated to URL")
        
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']"))
            )
            results["steps"].append("Feed found")
        except:
            results["steps"].append("Feed NOT found")
            return results

        time.sleep(5)
        
        # Capture hierarchy
        name_els = driver.find_elements(By.CSS_SELECTOR, ".qBF1Pd, .fontHeadlineSmall")
        results["names_found"] = len(name_els)
        
        if name_els:
            target = name_els[0]
            hierarchy = driver.execute_script("""
                var el = arguments[0];
                var path = [];
                while (el && el.tagName !== 'BODY') {
                    path.push({
                        tag: el.tagName,
                        classes: el.className,
                        role: el.getAttribute('role'),
                        jslog: el.getAttribute('jslog'),
                        jsaction: el.getAttribute('jsaction')
                    });
                    el = el.parentElement;
                }
                return path;
            """, target)
            results["hierarchy"] = hierarchy

        # Check markers
        markers = [".Nv2PK", ".hfpxzc", ".lI9IFe", "[role='article']", "div.m6QErb"]
        results["marker_counts"] = {}
        for m in markers:
            results["marker_counts"][m] = len(driver.find_elements(By.CSS_SELECTOR, m))

    except Exception as e:
        results["error"] = str(e)
    finally:
        driver.quit()
        
    with open("diagnostic_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    return results

if __name__ == "__main__":
    run_diagnostic()
