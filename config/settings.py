import os

BASE_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
COOKIES_DIR = os.path.join(BASE_DIR, "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)

# FOKUS PADA MBG TANPA FILTER WAKTU
KEYWORDS = ["MBG"]

# PRODUCTION SELENIUM SETTINGS
SELENIUM_DRIVER_PATH = r"D:/chromedriver-win64/chromedriver-win64/chromedriver.exe"  # SESUAIKAN LOKASI ANDA
BROWSER_HEADLESS = True  # Production mode - headless
SCROLL_DELAY = 3
PAGE_LOAD_DELAY = 5
MAX_POSTS = 1000  # Target 1000 data

# SCROLLING SETTINGS OPTIMAL UNTUK 1000 POST
MAX_SCROLL_ATTEMPTS = 40  # Cukup untuk 1000 post
SCROLL_RECOVERY_DELAY = 8
MIN_DELAY_BETWEEN_SCROLLS = 4
MAX_DELAY_BETWEEN_SCROLLS = 8

# SESSION MANAGEMENT
MAX_SESSION_DURATION = 1800  # 30 menit maksimal
SESSION_RESTART_THRESHOLD = 700  # Restart setelah 700 post

# OUTPUT SETTINGS
OUTPUT_FOLDER = os.path.abspath(os.path.join(PROJECT_ROOT, "output"))
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
OUTPUT_FORMAT = "csv"

# Load cookies
def load_cookies(filename):
    try:
        with open(os.path.join(COOKIES_DIR, filename), 'r', encoding='utf-8') as f:
            import json
            return json.load(f)
    except:
        return []

TWITTER_COOKIES = load_cookies("twitter_cookies.json")

print("====================================")
print("[PRODUCTION SETTINGS LOADED]")
print(f"Target keyword: 'MBG'")
print(f"Target posts: {MAX_POSTS}")
print(f"Max scroll attempts: {MAX_SCROLL_ATTEMPTS}")
print(f"Twitter cookies loaded: {len(TWITTER_COOKIES)}")
print(f"Headless mode: {'ENABLED' if BROWSER_HEADLESS else 'DISABLED'}")
print("====================================")