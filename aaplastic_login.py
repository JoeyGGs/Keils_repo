"""
All American Plastics - Automated Login Script
Logs into aaplastic.com, selects 'Deli' department, and leaves the browser open for ordering.

Usage:
    python aaplastic_login.py

Requires:
    - selenium
    - python-dotenv
    - Chrome browser installed
    
Credentials are loaded from a .env file in the project root:
    AAPLASTIC_USERNAME=YourCompany\YourUsername
    AAPLASTIC_PASSWORD=YourPassword
"""

import os
import sys
import time
from dotenv import load_dotenv

# Load environment variables from .env file (use script's directory to find it)
_script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_script_dir, ".env"))

AAPLASTIC_LOGIN_URL = "https://www.aaplastic.com/login"


def get_credentials():
    """Load AA Plastics credentials from environment variables."""
    username = os.getenv("AAPLASTIC_USERNAME", "")
    password = os.getenv("AAPLASTIC_PASSWORD", "")

    if not username or not password:
        print("ERROR: AA Plastics credentials not found.")
        print("Please set AAPLASTIC_USERNAME and AAPLASTIC_PASSWORD in your .env file.")
        print("")
        print("Example .env file:")
        print('  AAPLASTIC_USERNAME=YourCompany\\YourUsername')
        print("  AAPLASTIC_PASSWORD=YourPassword")
        sys.exit(1)

    return username, password


def create_driver(headless=False):
    """Create and return a configured Chrome WebDriver."""
    from selenium.webdriver.chrome.options import Options
    from selenium import webdriver

    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)  # Keep browser open
    chrome_options.add_argument("--start-maximized")
    if headless:
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(f"ERROR: Could not launch Chrome. Make sure Chrome is installed.")
        print(f"       Error: {e}")
        sys.exit(1)

    return driver


def do_login(driver):
    """Perform the login on an existing driver. Returns True on success."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    username, password = get_credentials()

    print(f"Navigating to {AAPLASTIC_LOGIN_URL}...")
    driver.get(AAPLASTIC_LOGIN_URL)

    wait = WebDriverWait(driver, 15)

    # Find the username/company field and password field
    username_field = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username'], input[name='user'], input[name='login'], input[type='text']"))
    )
    password_field = driver.find_element(By.CSS_SELECTOR, "input[name='password'], input[name='pass'], input[type='password']")

    print("Entering credentials...")
    username_field.clear()
    username_field.send_keys(username)
    password_field.clear()
    password_field.send_keys(password)

    # Click Sign In
    sign_in_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit'], .btn-login, button.sign-in")
    sign_in_button.click()

    time.sleep(3)

    current_url = driver.current_url
    if "login" in current_url.lower():
        print("WARNING: Still on the login page. Check your credentials.")
        print(f"         Current URL: {current_url}")
        return False
    else:
        print("SUCCESS! Logged into All American Plastics.")
        print(f"         Current URL: {current_url}")
        return True


def select_deli_department(driver):
    """After login, find and select the 'Deli' department from the dropdown."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC

    wait = WebDriverWait(driver, 10)
    print("Looking for department selector...")

    # The AA Plastics Order Management page has <select> dropdowns
    # First dropdown = department, second = store
    try:
        selects = wait.until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "select"))
        )
        for select_el in selects:
            sel = Select(select_el)
            for option in sel.options:
                if 'deli' in option.text.lower():
                    sel.select_by_visible_text(option.text)
                    print(f"Selected department: {option.text}")
                    time.sleep(2)
                    return True
    except Exception as e:
        print(f"  Could not find select dropdowns: {e}")

    print("Could not auto-select 'Deli' department — please select it manually.")
    return False


def tab_to_view_items(driver):
    """After Deli is selected, Tab 3 times from the dropdown to reach 'View Items' then Enter."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains

    print("Tabbing to 'View Items' button...")

    # Focus the Deli dropdown first so Tab starts from the right place
    try:
        selects = driver.find_elements(By.TAG_NAME, "select")
        if selects:
            selects[0].click()
            time.sleep(0.3)
    except Exception:
        pass

    actions = ActionChains(driver)
    # Tab 4 times: dropdown -> Store dropdown -> Start Order -> Skip Order -> View Items
    for i in range(4):
        actions.send_keys(Keys.TAB)
        actions.pause(0.3)
    actions.send_keys(Keys.ENTER)
    actions.perform()

    print("Pressed Tab x3 + Enter.")
    time.sleep(3)


def login():
    """Full login flow: open Chrome, sign in, select Deli department."""
    driver = create_driver()

    try:
        success = do_login(driver)
        if success:
            select_deli_department(driver)
            tab_to_view_items(driver)
            print("\nThe browser will stay open for you to place orders.")
            print("Close the browser window when you're done.")
    except Exception as e:
        print(f"ERROR during login: {e}")
        print("The browser is still open — you can try logging in manually.")

    return driver


if __name__ == "__main__":
    print("=" * 50)
    print("  All American Plastics - Auto Login")
    print("=" * 50)
    print()
    login()
