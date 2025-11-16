from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from config.settings import SELENIUM_DRIVER_PATH, BROWSER_HEADLESS

def create_driver():
    """Create and return a configured Chrome driver instance"""
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    if BROWSER_HEADLESS:
        options.add_argument("--headless")
    
    service = Service(SELENIUM_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    
    # Set default timeouts
    driver.implicitly_wait(10)
    return driver