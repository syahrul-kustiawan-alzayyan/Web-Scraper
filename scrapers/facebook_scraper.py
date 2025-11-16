from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
import os
from config.settings import (
    SELENIUM_DRIVER_PATH, 
    BROWSER_HEADLESS, 
    SCROLL_DELAY,
    PAGE_LOAD_DELAY,
    MAX_POSTS,
    FACEBOOK_COOKIES
)
from utils.scroller import scroll_page
from utils.parser import parse_facebook_post

class FacebookScraper:
    def __init__(self, keywords, output_folder, output_format="csv"):
        self.keywords = keywords
        self.output_folder = output_folder
        self.output_format = output_format
        self.driver = self._setup_driver()
        self.posts_data = []
        self.max_posts = MAX_POSTS

    def _setup_driver(self):
        options = Options()
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        if BROWSER_HEADLESS:
            options.add_argument("--headless")
        
        service = Service(SELENIUM_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(PAGE_LOAD_DELAY)
        return driver

    def _load_cookies(self):
        if not FACEBOOK_COOKIES:
            print("[WARNING] No Facebook cookies found. Login may be required")
            return False
            
        self.driver.get("https://www.facebook.com/")
        time.sleep(2)
        
        for cookie in FACEBOOK_COOKIES:
            try:
                self.driver.add_cookie(cookie)
            except Exception as e:
                print(f"Error adding cookie: {e}")
        
        self.driver.refresh()
        time.sleep(3)
        return True

    def _search_keyword(self, keyword):
        self.driver.get(f"https://www.facebook.com/search/posts/?q={keyword}")
        time.sleep(PAGE_LOAD_DELAY)
        
        # Handle login pop-up if appears
        try:
            not_now_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(),'Not Now')]"))
            )
            not_now_btn.click()
        except:
            pass

    def _extract_posts(self):
        posts = self.driver.find_elements(By.CSS_SELECTOR, 'div.x1y35706.x1n2onr6.xh8yej3')
        for post in posts:
            if len(self.posts_data) >= self.max_posts:
                break
                
            try:
                post_data = parse_facebook_post(post)
                if post_data:
                    self.posts_data.append(post_data)
            except Exception as e:
                print(f"Error parsing post: {e}")
                continue

    def run(self):
        try:
            if not self._load_cookies():
                print("[ERROR] Facebook login failed. Check cookies.")
                return

            for keyword in self.keywords:
                print(f"Searching Facebook for: {keyword}")
                self._search_keyword(keyword)
                scroll_page(self.driver, SCROLL_DELAY)
                self._extract_posts()

            self._save_results()
        finally:
            self.driver.quit()

    def _save_results(self):
        if not self.posts_data:
            print("No posts found to save")
            return
            
        df = pd.DataFrame(self.posts_data)
        output_file = os.path.join(
            self.output_folder, 
            f"facebook_results.{self.output_format}"
        )
        
        if self.output_format == "csv":
            df.to_csv(output_file, index=False)
        else:
            df.to_json(output_file, orient='records', indent=2)
            
        print(f"Saved {len(self.posts_data)} posts to {output_file}")