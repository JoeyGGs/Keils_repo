"""
All American Plastics - Submit Order Script
Logs in, selects Deli department, clicks 'Start Order',
then adds items from the current draft order to the AA Plastics cart.

Usage:
    python aaplastic_submit_order.py [order_id]
    
If no order_id is provided, uses the current draft order for V005.

Requires:
    - selenium
    - python-dotenv
    - Chrome browser installed
"""

import os
import sys
import json
import time

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_script_dir, ".env"))

from aaplastic_login import create_driver, do_login, select_deli_department

AA_VENDOR_ID = "V005"
DATA_DIR = os.path.join(_script_dir, "data")


def load_draft_order(order_id=None):
    """Load the draft order items from vendor_orders.json"""
    orders_file = os.path.join(DATA_DIR, "vendor_orders.json")
    if not os.path.exists(orders_file):
        print("ERROR: No vendor_orders.json found.")
        return None

    with open(orders_file, 'r', encoding='utf-8') as f:
        orders = json.load(f)

    if order_id:
        order = next((o for o in orders if o['id'] == order_id), None)
    else:
        # Find the draft order for AA Plastics
        order = next(
            (o for o in orders if o['vendor_id'] == AA_VENDOR_ID and o['status'] == 'draft'),
            None
        )

    if not order:
        print("ERROR: No draft order found for All American Plastics.")
        return None

    return order


def load_product_catalog():
    """Load the product catalog to get item codes for each product."""
    products_file = os.path.join(DATA_DIR, "vendor_products.json")
    if not os.path.exists(products_file):
        return {}

    with open(products_file, 'r', encoding='utf-8') as f:
        products = json.load(f)

    # Build lookup by product ID
    return {p['id']: p for p in products if p.get('vendor_id') == AA_VENDOR_ID}


def navigate_to_start_order(driver):
    """After Deli is selected, Tab twice then Enter to reach 'Start Order'."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains

    print("Tabbing to 'Start Order'...")

    # Click the first select (Deli dropdown) to set focus there
    try:
        selects = driver.find_elements(By.TAG_NAME, "select")
        if selects:
            selects[0].click()
            time.sleep(0.3)
    except Exception:
        pass

    # Tab three times then Enter
    actions = ActionChains(driver)
    actions.send_keys(Keys.TAB)
    actions.pause(0.3)
    actions.send_keys(Keys.TAB)
    actions.pause(0.3)
    actions.send_keys(Keys.TAB)
    actions.pause(0.3)
    actions.send_keys(Keys.ENTER)
    actions.perform()

    print("Pressed Enter on 'Start Order'.")
    time.sleep(3)


def set_item_quantity(driver, item_code, quantity):
    """Find an item by its item code on the order page and set the quantity."""
    from selenium.webdriver.common.by import By

    try:
        # AA Plastics order page typically has a table with item rows
        # Each row has the item code and a quantity input field
        # Try finding by item code text in the table
        rows = driver.find_elements(By.TAG_NAME, "tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            row_text = row.text.upper()

            # Check if this row contains our item code
            if item_code.upper() in row_text:
                # Find the quantity input in this row
                qty_inputs = row.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number'], input[name*='qty'], input[name*='Qty'], input[name*='quantity']")
                if qty_inputs:
                    qty_input = qty_inputs[0]
                    qty_input.clear()
                    qty_input.send_keys(str(quantity))
                    print(f"  ✓ Set qty {quantity} for item {item_code}")
                    return True

        # Fallback: try finding input by name/id containing the item code
        try:
            inputs = driver.find_elements(By.CSS_SELECTOR, f"input[name*='{item_code}'], input[id*='{item_code}']")
            if inputs:
                inputs[0].clear()
                inputs[0].send_keys(str(quantity))
                print(f"  ✓ Set qty {quantity} for item {item_code} (by input name)")
                return True
        except Exception:
            pass

        print(f"  ✗ Could not find item {item_code} on the order page")
        return False

    except Exception as e:
        print(f"  ✗ Error setting qty for {item_code}: {e}")
        return False


def submit_order():
    """Full order submission flow."""
    # Load the order
    order_id = sys.argv[1] if len(sys.argv) > 1 else None
    order = load_draft_order(order_id)
    if not order:
        return

    items = order.get('items', [])
    if not items:
        print("ERROR: Order has no items.")
        return

    # Load product catalog for item codes
    catalog = load_product_catalog()

    # Map order items to their AA Plastics item codes
    order_items = []
    for item in items:
        product = catalog.get(item['product_id'], {})
        item_code = product.get('item_code', '') or product.get('sku', '') or item.get('sku', '')
        if item_code:
            order_items.append({
                'name': item['product_name'],
                'item_code': item_code,
                'quantity': item['quantity'],
            })
        else:
            print(f"  WARNING: No item code for '{item['product_name']}' — will try by name")
            order_items.append({
                'name': item['product_name'],
                'item_code': item['product_name'],
                'quantity': item['quantity'],
            })

    print(f"\nOrder has {len(order_items)} items to submit.")
    print("-" * 40)
    for oi in order_items:
        print(f"  {oi['item_code']:>10}  x{oi['quantity']}  {oi['name']}")
    print("-" * 40)
    print()

    # Launch browser, login, select Deli, Start Order
    driver = create_driver()

    try:
        success = do_login(driver)
        if not success:
            print("Login failed. Browser stays open for manual ordering.")
            return

        select_deli_department(driver)
        navigate_to_start_order(driver)

        # Now fill in quantities for each item
        print("\nSetting item quantities...")
        filled = 0
        missed = 0
        for oi in order_items:
            if set_item_quantity(driver, oi['item_code'], oi['quantity']):
                filled += 1
            else:
                missed += 1
            time.sleep(0.3)

        print(f"\nDone! {filled} items filled, {missed} items not found.")
        if missed > 0:
            print("Items not found may need to be entered manually on the website.")
        print()
        print("=" * 50)
        print("  ORDER NOT SUBMITTED — REVIEW MODE")
        print("  Review all items and quantities in the browser.")
        print("  When ready, click Submit on the AA Plastics site.")
        print("=" * 50)

    except Exception as e:
        print(f"ERROR during order submission: {e}")
        print("The browser is still open — you can complete the order manually.")


if __name__ == "__main__":
    print("=" * 50)
    print("  All American Plastics - Submit Order")
    print("=" * 50)
    print()
    submit_order()
