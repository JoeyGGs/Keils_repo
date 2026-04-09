"""
All American Plastics - Catalog Scraper
Logs in, selects Deli department, navigates to 'View Items', and
scrapes the full catalog into the internal vendor_products.json.

Usage:
    python aaplastic_scrape_catalog.py

Requires:
    - selenium
    - python-dotenv
    - Chrome browser installed
"""

import os
import sys
import json
import time
import uuid
from datetime import datetime

# Reuse login helpers from the login script
_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_script_dir, ".env"))

from aaplastic_login import create_driver, do_login, select_deli_department, tab_to_view_items

# The vendor ID for All American Plastics in vendors.json
AA_VENDOR_ID = "V005"
DATA_DIR = os.path.join(_script_dir, "data")
PRODUCTS_FILE = os.path.join(DATA_DIR, "vendor_products.json")


def navigate_to_view_items(driver):
    """After department selection, hover over then click the 'View Items' button.
    Uses Tab key navigation and ActionChains hover as the primary strategies
    since the button may require a hover/focus state before it activates."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    wait = WebDriverWait(driver, 10)
    actions = ActionChains(driver)
    print("Looking for 'View Items' button...")

    # First, find the element
    view_items_el = None

    # Try multiple ways to locate the element
    locators = [
        (By.XPATH, "//button[normalize-space()='View Items']"),
        (By.XPATH, "//a[normalize-space()='View Items']"),
        (By.XPATH, "//input[@value='View Items']"),
        (By.XPATH, "//*[normalize-space()='View Items']"),
        (By.XPATH, "//*[contains(normalize-space(),'View Items')]"),
    ]

    for by, selector in locators:
        try:
            view_items_el = wait.until(EC.presence_of_element_located((by, selector)))
            print(f"  Found element: <{view_items_el.tag_name}> '{view_items_el.text.strip()}'")
            break
        except Exception:
            continue

    if view_items_el:
        # Strategy 1: Hover over it, pause, then click
        try:
            print("  Hovering over 'View Items'...")
            actions.move_to_element(view_items_el).pause(1).click().perform()
            print("  Hover + click performed.")
            time.sleep(3)
            if _page_changed(driver):
                return True
        except Exception as e:
            print(f"  Hover+click failed: {e}")

        # Strategy 2: Scroll into view, then JavaScript click
        try:
            print("  Trying JavaScript click...")
            driver.execute_script("arguments[0].scrollIntoView(true);", view_items_el)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", view_items_el)
            print("  JS click performed.")
            time.sleep(3)
            if _page_changed(driver):
                return True
        except Exception as e:
            print(f"  JS click failed: {e}")

        # Strategy 3: Dispatch mouse events manually via JS
        try:
            print("  Dispatching mouseover + click events via JS...")
            driver.execute_script("""
                var el = arguments[0];
                el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                el.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
                el.dispatchEvent(new MouseEvent('mousemove', {bubbles: true}));
            """, view_items_el)
            time.sleep(1)
            driver.execute_script("""
                var el = arguments[0];
                el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                el.dispatchEvent(new MouseEvent('click', {bubbles: true}));
            """, view_items_el)
            print("  JS events dispatched.")
            time.sleep(3)
            if _page_changed(driver):
                return True
        except Exception as e:
            print(f"  JS event dispatch failed: {e}")

    # Strategy 4: Tab through focusable elements until we reach "View Items", then Enter
    print("  Trying Tab key navigation...")
    try:
        # Start from body
        body = driver.find_element(By.TAG_NAME, "body")
        body.click()
        time.sleep(0.3)

        for i in range(30):  # Tab up to 30 times
            actions.send_keys(Keys.TAB).perform()
            time.sleep(0.2)
            focused = driver.switch_to.active_element
            focused_text = focused.text.strip() or focused.get_attribute('value') or ''
            if 'view items' in focused_text.lower():
                print(f"  Tab focused on: '{focused_text}' — pressing Enter...")
                actions.send_keys(Keys.ENTER).perform()
                time.sleep(3)
                return True
    except Exception as e:
        print(f"  Tab navigation failed: {e}")

    # Strategy 5: Find all clickable elements, hover each, check for View Items
    try:
        all_clickables = driver.find_elements(By.CSS_SELECTOR,
            "button, a, input[type='button'], input[type='submit'], [role='button']")
        for el in all_clickables:
            el_text = el.text.strip() or el.get_attribute('value') or ''
            if 'view' in el_text.lower() and 'item' in el_text.lower():
                print(f"  Found clickable: '{el_text}' — hovering then clicking...")
                actions = ActionChains(driver)
                actions.move_to_element(el).pause(1).click().perform()
                time.sleep(3)
                return True
    except Exception:
        pass

    print("WARNING: Could not find or activate 'View Items' — trying to scrape current page.")
    return False


def _page_changed(driver):
    """Quick check if the page content changed (new content loaded)."""
    from selenium.webdriver.common.by import By
    try:
        # Look for signs that a catalog/items page loaded
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        # If we see table headers or product-like content, assume success
        if any(kw in body_text for kw in ['item #', 'item no', 'description', 'price', 'qty', 'uom', 'pack']):
            print("  Page appears to have loaded catalog content.")
            return True
    except Exception:
        pass
    return False


def scrape_catalog_page(driver):
    """
    Scrape product data from the AA Plastics 'View Items' table.
    Table columns: Image | Description | Size | Item # | Code | Qty
    Also grabs the <img> src from each row.
    Returns a list of dicts.
    """
    from selenium.webdriver.common.by import By

    products = []
    print("Scraping catalog items from current page...")

    # Find the product table
    tables = driver.find_elements(By.CSS_SELECTOR, "table")
    if not tables:
        print("  No tables found on page.")
        return products

    for table in tables:
        rows = table.find_elements(By.CSS_SELECTOR, "tbody tr, tr")

        for row in rows:
            cells = row.find_elements(By.CSS_SELECTOR, "td")
            if len(cells) < 4:
                continue

            # Try to grab the image from the first cell (or anywhere in the row)
            image_url = ""
            try:
                img = row.find_element(By.CSS_SELECTOR, "img")
                image_url = img.get_attribute("src") or ""
            except Exception:
                pass

            # The table has columns: Image | Description | Size | Item # | Code | Qty
            # But headers may vary — find the text cells
            text_cells = []
            for cell in cells:
                text = cell.text.strip()
                # Skip cells that are just the image (empty text and has img)
                if not text:
                    try:
                        cell.find_element(By.CSS_SELECTOR, "img")
                        continue  # It's the image column, skip
                    except Exception:
                        pass
                text_cells.append(text)

            if not text_cells:
                continue

            # Map text cells to fields based on position
            # Expected order after skipping image: Description, Size, Item #, Code, Qty?
            description = text_cells[0] if len(text_cells) > 0 else ""
            size = text_cells[1] if len(text_cells) > 1 else ""
            item_number = text_cells[2] if len(text_cells) > 2 else ""
            code = text_cells[3] if len(text_cells) > 3 else ""

            # Skip header rows
            if description.lower() in ('description', 'item', 'product', 'name'):
                continue

            if description:
                products.append({
                    'description': description,
                    'size': size,
                    'item_number': item_number,
                    'code': code,
                    'image_url': image_url,
                })

        if products:
            print(f"  Found {len(products)} items in table.")
            return products

    # If no table worked, grab from page body as fallback
    if not products:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        if len(lines) > 5:
            print(f"  Fallback: captured {len(lines)} text lines from the page.")
            for line in lines:
                products.append({'raw_text': line})

    return products


def handle_pagination(driver):
    """Click through all pages and scrape each one. Returns combined product list."""
    from selenium.webdriver.common.by import By

    all_products = []

    page_num = 1
    while True:
        print(f"\n--- Page {page_num} ---")
        page_products = scrape_catalog_page(driver)
        all_products.extend(page_products)

        # Try to find and click "Next" page button
        next_clicked = False
        for selector in [
            "a.next", "a.page-next", ".pagination .next a",
            "a[rel='next']", "button.next", "[aria-label='Next']",
            "a:contains('Next')", "a:contains('»')", "a:contains('>')",
        ]:
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, selector)
                if next_btn.is_displayed() and next_btn.is_enabled():
                    next_btn.click()
                    time.sleep(2)
                    next_clicked = True
                    page_num += 1
                    break
            except Exception:
                continue

        # Also try XPath for "Next" text
        if not next_clicked:
            try:
                next_el = driver.find_element(By.XPATH,
                    "//a[contains(text(),'Next')] | //button[contains(text(),'Next')] | "
                    "//a[contains(text(),'»')] | //a[contains(text(),'>')]")
                if next_el.is_displayed() and next_el.is_enabled():
                    next_el.click()
                    time.sleep(2)
                    next_clicked = True
                    page_num += 1
            except Exception:
                pass

        if not next_clicked:
            break

    return all_products


def normalize_products(raw_products):
    """
    Convert raw scraped data into VendorProduct-compatible dicts.
    Fields from scraper: description, size, item_number, code, image_url
    """
    import re
    normalized = []

    for raw in raw_products:
        if not isinstance(raw, dict):
            continue

        description = raw.get('description', '').strip()
        size = raw.get('size', '').strip()
        item_number = raw.get('item_number', '').strip()
        code = raw.get('code', '').strip()
        image_url = raw.get('image_url', '').strip()

        # Skip empty rows or header rows
        if not description or description.lower() in ('description', 'item', 'name'):
            continue

        # Use item_number as SKU (e.g., AAI-18FOILHD)
        # Use code as the numeric item code (e.g., 613303)
        normalized.append({
            'id': str(uuid.uuid4())[:8].upper(),
            'vendor_id': AA_VENDOR_ID,
            'name': description,
            'sku': item_number,
            'description': '',
            'category': 'DELI SUPPLIES',
            'unit': 'each',
            'pack_size': size,
            'cost': 0.0,
            'is_active': True,
            'image_url': image_url,
            'item_code': code,
        })

    return normalized


def save_to_catalog(new_products):
    """Merge scraped products into existing vendor_products.json."""
    os.makedirs(DATA_DIR, exist_ok=True)

    existing = []
    if os.path.exists(PRODUCTS_FILE):
        try:
            with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []

    # Remove old AA Plastics products (we're replacing the whole catalog)
    other_vendor_products = [p for p in existing if p.get('vendor_id') != AA_VENDOR_ID]

    combined = other_vendor_products + new_products

    with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(new_products)} AA Plastics products to catalog.")
    print(f"Total products across all vendors: {len(combined)}")
    return len(new_products)


def run_scraper():
    """Full scrape flow: login → deli → view items → scrape → save."""
    print("=" * 55)
    print("  All American Plastics - Catalog Scraper")
    print("=" * 55)
    print()

    driver = create_driver(headless=False)

    try:
        # Step 1: Login
        success = do_login(driver)
        if not success:
            print("Login failed. Aborting.")
            return

        # Step 2: Select Deli department
        select_deli_department(driver)
        time.sleep(2)

        # Step 3: Tab to View Items and press Enter
        tab_to_view_items(driver)
        time.sleep(2)

        # Step 4: Scrape all pages
        print("\n" + "-" * 40)
        print("  SCRAPING CATALOG")
        print("-" * 40)
        raw_products = handle_pagination(driver)

        if not raw_products:
            print("\nNo products found on the page.")
            print("Current URL:", driver.current_url)
            print("\nPage source saved to aaplastic_debug.html for inspection.")
            with open(os.path.join(_script_dir, "aaplastic_debug.html"), 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            return

        print(f"\nRaw items scraped: {len(raw_products)}")

        # Step 5: Normalize and save
        products = normalize_products(raw_products)
        print(f"Normalized products: {len(products)}")

        if products:
            count = save_to_catalog(products)
            print(f"\n✓ Successfully imported {count} products into the internal catalog!")
            print(f"  View them in the ordering page under All American Plastics.")
        else:
            print("\nCould not normalize any products. Saving raw data for review...")
            raw_file = os.path.join(DATA_DIR, "aaplastic_raw_scrape.json")
            with open(raw_file, 'w', encoding='utf-8') as f:
                json.dump(raw_products, f, indent=2, ensure_ascii=False)
            print(f"  Raw data saved to: {raw_file}")

    except Exception as e:
        print(f"\nERROR during scraping: {e}")
        import traceback
        traceback.print_exc()
        # Save page source for debugging
        try:
            with open(os.path.join(_script_dir, "aaplastic_debug.html"), 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print("Page source saved to aaplastic_debug.html for debugging.")
        except Exception:
            pass
    finally:
        print("\nBrowser will stay open. Close it manually when done.")


if __name__ == "__main__":
    run_scraper()
