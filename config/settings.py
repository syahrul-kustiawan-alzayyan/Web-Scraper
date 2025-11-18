import json
import os
from datetime import datetime, timedelta

# Get the directory of this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
COOKIES_DIR = os.path.join(BASE_DIR, "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)

def load_json(filename, base_dir=BASE_DIR):
    """Load JSON file dengan error handling yang lebih baik"""
    path = os.path.join(base_dir, filename)
    
    if not os.path.exists(path):
        print(f"[WARNING] File {filename} not found at {path}")
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"[ERROR] Failed to load {filename}: {e}")
        return None

# Load keywords dengan penanganan struktur yang fleksibel
keywords_data = load_json("keywords.json")

if keywords_data:
    if isinstance(keywords_data, list):
        KEYWORDS = keywords_data
    elif isinstance(keywords_data, dict) and "mbg_keywords" in keywords_data:   
        KEYWORDS = keywords_data["mbg_keywords"]
    elif isinstance(keywords_data, dict) and len(keywords_data) > 0:
        KEYWORDS = list(keywords_data.values())[0]
    else:
        KEYWORDS = ["mbg prabowo"]
else:
    KEYWORDS = ["mbg prabowo"]

# PRODUCTION SELENIUM SETTINGS - UNLIMITED MODE
SELENIUM_DRIVER_PATH = r"D:/chromedriver-win64/chromedriver-win64/chromedriver.exe"
BROWSER_HEADLESS = False
SCROLL_DELAY = 3
PAGE_LOAD_DELAY = 4

# 🚫 UNLIMITED MODE - NO POST LIMIT
MAX_POSTS = float('inf')  # INFINITE POSTS
MAX_SCROLL_ATTEMPTS = 250  # Increased for unlimited mode
SCROLL_RECOVERY_DELAY = 10
MIN_DELAY_BETWEEN_SCROLLS = 4
MAX_DELAY_BETWEEN_SCROLLS = 8
SESSION_RESTART_THRESHOLD = 1000
MAX_SESSION_DURATION = 21600  # 6 hours

# Load cookies
def load_cookies(filename):
    try:
        with open(os.path.join(COOKIES_DIR, filename), 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

TWITTER_COOKIES = load_cookies("twitter_cookies.json")
INSTAGRAM_COOKIES = load_cookies("instagram_cookies.json")
FACEBOOK_COOKIES = load_cookies("facebook_cookies.json")

# Output settings
OUTPUT_FOLDER = os.path.abspath(os.path.join(PROJECT_ROOT, "output"))
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
OUTPUT_FORMAT = "csv"

print("====================================")
print("[UNLIMITED SCRAPER SETTINGS LOADED]")
print(f"Keywords loaded: {len(KEYWORDS)} items")
print(f"   Keywords: {KEYWORDS}")
print(f"Twitter cookies loaded: {len(TWITTER_COOKIES)}")
print("🚀 UNLIMITED MODE: No post limit - will collect ALL available posts")
print("====================================")