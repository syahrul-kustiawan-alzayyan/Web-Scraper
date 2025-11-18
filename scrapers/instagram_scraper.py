from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import time
import pandas as pd
import os
import random
from datetime import datetime
import json
import urllib.parse
import re
from config.settings import (
    SELENIUM_DRIVER_PATH,
    BROWSER_HEADLESS,
    SCROLL_DELAY,
    PAGE_LOAD_DELAY,
    MAX_POSTS,
    INSTAGRAM_COOKIES,
    OUTPUT_FOLDER,
    OUTPUT_FORMAT,
    KEYWORDS
)

class InstagramScraper:
    def __init__(self):
        self.driver = None
        self.posts_data = []
        self.processed_posts = set()
        self.start_time = None
        self.scroll_attempts = 0
        self.target_keyword = KEYWORDS[0] if KEYWORDS else "program mbg"
        self.current_search_strategy = "hashtag"
        self.last_valid_post_url = None

    def _setup_driver(self):
        """Setup Chrome driver dengan konfigurasi Instagram-friendly"""
        print("🔧 Setting up Instagram Chrome driver...")
        options = Options()
        
        # Essential options for Instagram
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-renderer-backgrounding")
        
        # Performance optimization
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-automation")
        
        # Anti-detection settings
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # User agent Instagram mobile (paling efektif)
        options.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36 Instagram 299.0.0.28.99 Android (30/11; 420dpi; 1080x2247; samsung; SM-G973F; beyond1; exynos9820; en_US; 460200385)")
        
        if BROWSER_HEADLESS:
            options.add_argument("--headless=new")
        
        service = Service(SELENIUM_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
        
        # Extra anti-detection
        driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined
        });
        window.navigator.webdriver = undefined;
        Object.defineProperty(navigator, 'plugins', {
          get: () => [1, 2, 3, 4, 5]
        });
        Object.defineProperty(navigator, 'languages', {
          get: () => ['en-US', 'en']
        });
        """)
        
        print("✅ Instagram Chrome driver initialized")
        return driver

    def _is_valid_post_url(self, url):
        """Check if URL is a valid Instagram post URL (not like/like_by/comments)"""
        if not url:
            return False
        return "/p/" in url and not ("/liked_by/" in url or "/comments/" in url or "/liked/" in url)

    def _get_valid_post_url(self, post_element):
        """Get only valid post URL (avoiding like/like_by URLs)"""
        print("   🔍 Getting valid post URL...")
        valid_url = None
        
        # Strategy 1: Find direct post link
        try:
            post_link = post_element.find_element(By.CSS_SELECTOR, "a[href*='/p/']:not([href*='/liked_by/']):not([href*='/comments/'])")
            url = post_link.get_attribute("href")
            if self._is_valid_post_url(url):
                valid_url = url
                print(f"   ✅ Found valid post URL: {valid_url}")
        except:
            pass
        
        # Strategy 2: Find ancestor post link
        if not valid_url:
            try:
                parent_link = post_element.find_element(By.XPATH, "./ancestor::a[contains(@href, '/p/') and not(contains(@href, '/liked_by/'))]")
                url = parent_link.get_attribute("href")
                if self._is_valid_post_url(url):
                    valid_url = url
                    print(f"   ✅ Found valid post URL from ancestor: {valid_url}")
            except:
                pass
        
        # Strategy 3: Check for multiple links
        if not valid_url:
            try:
                links = post_element.find_elements(By.CSS_SELECTOR, "a[href*='/p/']")
                for link in links:
                    url = link.get_attribute("href")
                    if self._is_valid_post_url(url):
                        valid_url = url
                        print(f"   ✅ Found valid post URL from multiple links: {valid_url}")
                        break
            except:
                pass
        
        if valid_url:
            self.last_valid_post_url = valid_url
            return valid_url
        return None

    def _handle_wrong_page(self):
        """Handle being on wrong page (liked_by, comments, etc.)"""
        current_url = self.driver.current_url
        print(f"   ⚠️ On wrong page: {current_url}")
        
        try:
            # Try to close modal if open
            self._close_modal_if_open()
            time.sleep(1)
            
            # Try to go back to previous page
            self.driver.back()
            time.sleep(3)
            
            # Check if we're on the correct page now
            if self._is_valid_post_url(self.driver.current_url):
                print("   ✅ Successfully returned to post page")
                return True
        except:
            pass
        
        # Try to find and click the actual post link
        try:
            # Look for the post link in the current context
            post_link = self.driver.find_element(By.CSS_SELECTOR, "a[href*='/p/']:not([href*='/liked_by/'])")
            post_link.click()
            time.sleep(3)
            if self._is_valid_post_url(self.driver.current_url):
                print("   ✅ Successfully navigated to post page")
                return True
        except:
            pass
        
        # Final fallback: Navigate to last known valid post URL
        if self.last_valid_post_url:
            try:
                print(f"   🌐 Navigating to last valid post URL: {self.last_valid_post_url}")
                self.driver.get(self.last_valid_post_url)
                time.sleep(3)
                if self._is_valid_post_url(self.driver.current_url):
                    print("   ✅ Successfully navigated to last valid post URL")
                    return True
            except:
                pass
        
        print("   ❌ Failed to return to post page")
        return False

    def _load_cookies(self):
        """Load Instagram cookies dengan validasi ekstra"""
        print("🍪 Loading Instagram cookies...")
        
        if not INSTAGRAM_COOKIES:
            print("[ERROR] No Instagram cookies found. Scraping cannot proceed.")
            return False
            
        try:
            # Navigate to Instagram first
            self.driver.get("https://www.instagram.com/")
            time.sleep(PAGE_LOAD_DELAY)
            
            # Clear existing cookies
            self.driver.delete_all_cookies()
            print("   Cleared existing cookies")
            
            # Add cookies with domain fix
            valid_cookies = 0
            for cookie in INSTAGRAM_COOKIES:
                try:
                    cookie = cookie.copy()
                    # Fix domain for Instagram
                    if 'domain' in cookie:
                        cookie['domain'] = cookie['domain'].replace('.instagram.com', 'instagram.com')
                        cookie['domain'] = cookie['domain'].lstrip('.')
                    
                    if 'name' not in cookie or 'value' not in cookie:
                        continue
                    
                    # Fix URL encoded characters in sessionid
                    if cookie['name'] == 'sessionid':
                        cookie['value'] = cookie['value'].replace('%3A', ':')
                    
                    # Add required fields
                    cookie.setdefault('path', '/')
                    cookie.setdefault('secure', True)
                    cookie.setdefault('httpOnly', False)
                    
                    self.driver.add_cookie(cookie)
                    valid_cookies += 1
                except Exception as e:
                    print(f"   ❌ Error adding cookie: {str(e)}")
            
            print(f"   ✅ Added {valid_cookies}/{len(INSTAGRAM_COOKIES)} valid cookies")
            
            # Refresh to apply cookies
            print("   Refreshing page to apply cookies...")
            self.driver.refresh()
            time.sleep(PAGE_LOAD_DELAY * 2)
            
            # Verify login status
            return self._verify_instagram_login()
                
        except Exception as e:
            print(f"❌ [ERROR] Instagram cookie loading failed: {str(e)}")
            self.driver.save_screenshot("instagram_cookie_error.png")
            return False

    def _verify_instagram_login(self):
        """Verifikasi Instagram login dengan multiple strategies"""
        print("   🔍 Verifying Instagram login status...")
        
        try:
            # Strategy 1: Check for create post button
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[aria-label='New Post'], [aria-label='Postingan Baru']"))
                )
                print("   ✅ Login verified via create post button")
                return True
            except:
                pass
            
            # Strategy 2: Check for profile icon
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[aria-label='Profile'], [aria-label='Profil']"))
                )
                print("   ✅ Login verified via profile icon")
                return True
            except:
                pass
            
            # Strategy 3: Check for home feed
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
                )
                print("   ✅ Login verified via home feed")
                return True
            except:
                pass
            
            # Strategy 4: Check current URL
            current_url = self.driver.current_url
            if "instagram.com/" in current_url and not any(x in current_url for x in ["login", "challenge"]):
                print("   ✅ Login verified via URL check")
                return True
            
            print("   ❌ Login verification failed - taking debug screenshot")
            self.driver.save_screenshot("instagram_login_verification_failed.png")
            return False
            
        except Exception as e:
            print(f"   ❌ Login verification failed: {str(e)}")
            self.driver.save_screenshot("instagram_verification_failed.png")
            return False

    def _close_all_popups(self):
        """Close ALL types of Instagram popups with aggressive approach"""
        print("   🧹 AGGRESSIVE POPUP CLOSING...")
        
        # Common popup button texts (English and Indonesian)
        popup_button_texts = [
            "Not Now", "Not now", "Bukan Sekarang", "Not Now.",
            "Save Info", "Save info", "Simpan Info", "Save Info.",
            "Accept", "Accept All", "Terima", "Accept.",
            "Log In", "Log in", "Masuk", "Log In.",
            "Cancel", "Batal", "Cancel.", "Close", "Tutup"
        ]
        
        # Try to close popups for 10 seconds max
        start_time = time.time()
        closed_any = False
        
        while time.time() - start_time < 10:
            popup_closed = False
            
            # Strategy 1: Close by button text
            for text in popup_button_texts:
                try:
                    # Cari button dengan teks spesifik
                    buttons = self.driver.find_elements(By.XPATH, f"//button[contains(text(), '{text}')]")
                    for button in buttons:
                        if button.is_displayed() and button.is_enabled():
                            print(f"   ✅ Closing popup with button: '{text}'")
                            button.click()
                            time.sleep(1.5)
                            popup_closed = True
                            closed_any = True
                            break
                    if popup_closed:
                        break
                except:
                    continue
            
            # Strategy 2: Close by aria-label
            if not popup_closed:
                try:
                    close_buttons = self.driver.find_elements(By.CSS_SELECTOR, "[aria-label*='Close'], [aria-label*='Tutup'], [aria-label*='close']")
                    for btn in close_buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            print("   ✅ Closing popup via aria-label")
                            btn.click()
                            time.sleep(1.5)
                            popup_closed = True
                            closed_any = True
                            break
                except:
                    pass
            
            # Strategy 3: Close by class name patterns
            if not popup_closed:
                try:
                    close_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[type='button'], div[role='button']")
                    for btn in close_buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            # Cek jika button terlihat sebagai tombol close
                            btn_text = btn.text.strip().lower()
                            if any(word in btn_text for word in ["close", "tutup", "cancel", "batal", "x"]):
                                print("   ✅ Closing popup via button text pattern")
                                btn.click()
                                time.sleep(1.5)
                                popup_closed = True
                                closed_any = True
                                break
                except:
                    pass
            
            # Jika tidak ada popup yang ditutup dalam iterasi ini, break
            if not popup_closed:
                break
        
        if closed_any:
            print("   ✅ Successfully closed popups")
        else:
            print("   ℹ️ No popups found or all already closed")

    def _handle_instagram_redirects(self):
        """Handle common Instagram redirects and challenges"""
        print("   🔁 Handling Instagram redirects...")
        
        current_url = self.driver.current_url.lower()
        
        # Handle login redirects
        if "login" in current_url or "challenge" in current_url:
            print("   ⚠️ Redirected to login page. Attempting to recover...")
            
            # Try to go back to previous page
            try:
                self.driver.back()
                time.sleep(3)
                print("   ✅ Navigated back from login redirect")
                return True
            except:
                pass
        
        # Handle checkpoint/challenge
        if "checkpoint" in current_url or "challenge" in current_url:
            print("   ⚠️ Instagram checkpoint detected. Taking screenshot...")
            self.driver.save_screenshot("instagram_checkpoint.png")
            return False
        
        # Handle rate limiting
        if "rate_limit" in current_url or "blocked" in current_url:
            print("   ⚠️ Instagram rate limiting detected. Taking screenshot...")
            self.driver.save_screenshot("instagram_rate_limit.png")
            return False
        
        return True

    def search_keyword(self):
        """Search Instagram dengan multiple strategies untuk 'program mbg'"""
        print(f"\n🔍 Searching Instagram for: '{self.target_keyword}'")
        
        # Daftar strategi pencarian
        search_strategies = [
            {
                "name": "hashtag_cleaned",
                "url": f"https://www.instagram.com/explore/tags/{self.target_keyword.replace(' ', '').replace('mbg', 'mbg').lower()}/",
                "description": "Hashtag cleaned (no spaces)"
            },
            {
                "name": "hashtag_with_underscore",
                "url": f"https://www.instagram.com/explore/tags/{self.target_keyword.replace(' ', '_').lower()}/",
                "description": "Hashtag with underscore"
            },
            {
                "name": "search_page",
                "url": f"https://www.instagram.com/web/search/topsearch/?query={urllib.parse.quote(self.target_keyword)}",
                "description": "Search page API"
            },
            {
                "name": "explore_page",
                "url": "https://www.instagram.com/explore/",
                "description": "Explore page (fallback)"
            }
        ]
        
        for strategy in search_strategies:
            print(f"\n🎯 Trying search strategy: {strategy['name']}")
            print(f"   📌 {strategy['description']}")
            print(f"   💻 URL: {strategy['url']}")
            
            try:
                self.driver.get(strategy['url'])
                time.sleep(PAGE_LOAD_DELAY * 2)
                
                # Handle popups
                self._close_all_popups()
                
                # Check if search results loaded
                if self._check_search_results_loaded(strategy['name']):
                    print(f"✅ Search results loaded successfully with strategy: {strategy['name']}")
                    self.current_search_strategy = strategy['name']
                    return True
                else:
                    print(f"❌ Search results not found with strategy: {strategy['name']}")
                    self.driver.save_screenshot(f"instagram_search_{strategy['name']}_failed.png")
                    time.sleep(2)
                    continue
                    
            except Exception as e:
                print(f"❌ Search failed with strategy {strategy['name']}: {str(e)}")
                self.driver.save_screenshot(f"instagram_search_{strategy['name']}_error.png")
                time.sleep(3)
                continue
        
        print("❌ All search strategies failed")
        return False

    def _check_search_results_loaded(self, strategy_name):
        """Periksa apakah hasil pencarian sudah termuat"""
        try:
            if strategy_name in ["hashtag_cleaned", "hashtag_with_underscore"]:
                # Check for hashtag page posts
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article, div._aabd, div._aagv img"))
                )
                
                # Check if there are actual posts
                posts = self.driver.find_elements(By.CSS_SELECTOR, "article, div._aabd, div._aagv img")
                if len(posts) > 0:
                    print(f"   ✅ Found {len(posts)} posts on hashtag page")
                    return True
                
            elif strategy_name == "search_page":
                # Check for search results
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='dialog'], div[role='presentation'], a[href*='/p/']"))
                )
                print("   ✅ Search API results loaded")
                return True
                
            elif strategy_name == "explore_page":
                # Check for explore page content
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article, div[class*='_aagv']"))
                )
                print("   ✅ Explore page loaded successfully")
                return True
            
            return False
            
        except Exception as e:
            print(f"   ❌ Search results check failed: {str(e)}")
            return False

    def _smart_scroll_until_target(self):
        """Scrolling cerdas untuk Instagram hingga 1000 post"""
        print(f"\n🔄 Starting smart scrolling for 1000 Instagram posts of '{self.target_keyword}'...")
        print("=" * 70)
        
        self.start_time = time.time()
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        no_new_content_count = 0
        
        # Strategi scrolling berdasarkan jenis halaman
        if self.current_search_strategy in ["hashtag_cleaned", "hashtag_with_underscore"]:
            max_scrolls = 25
            scroll_increment = "window.innerHeight * 1.5"
        else:
            max_scrolls = 15
            scroll_increment = "window.innerHeight"
        
        while (self.scroll_attempts < max_scrolls and 
               len(self.posts_data) < MAX_POSTS and
               time.time() - self.start_time < 1800):  # 30 minutes max
            
            self.scroll_attempts += 1
            elapsed_time = time.time() - self.start_time
            print(f"\n📈 Scroll Attempt {self.scroll_attempts}/{max_scrolls} | Elapsed: {elapsed_time:.1f}s")
            print(f"   Current posts: {len(self.posts_data)}/{MAX_POSTS}")
            
            try:
                # Scroll in small increments (Instagram needs gentle scrolling)
                print("   ⬇️ Scrolling page...")
                for i in range(2):
                    self.driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
                    time.sleep(1.2)
                
                # Wait for content to load
                time.sleep(SCROLL_DELAY)
                
                # Check if we're on the wrong page
                if not self._is_valid_post_url(self.driver.current_url):
                    print("   ⚠️ Detected wrong page during scrolling - attempting to recover")
                    self._handle_wrong_page()
                
                # Extract posts
                new_posts = self._extract_posts()
                print(f"   📊 This scroll: {new_posts} new posts | Total: {len(self.posts_data)}")
                
                # Check if we reached bottom
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    no_new_content_count += 1
                    print(f"   ⚠️ No new content ({no_new_content_count}/3)")
                    
                    if no_new_content_count >= 3:
                        print("   🛑 Stopping scroll - no new content after 3 attempts")
                        break
                else:
                    no_new_content_count = 0
                    last_height = new_height
                
                # Random delay to avoid detection
                delay = random.uniform(1.5, 3.5)
                print(f"   ⏳ Waiting {delay:.1f}s before next scroll...")
                time.sleep(delay)
                
            except Exception as e:
                print(f"   ❌ Scroll attempt failed: {str(e)}")
                time.sleep(5)
        
        print("\n✅ Instagram scrolling completed")
        print(f"   Total scroll attempts: {self.scroll_attempts}")
        print(f"   Total posts extracted: {len(self.posts_data)}")
        print(f"   Session duration: {time.time() - self.start_time:.1f} seconds")

    def _get_post_id(self, post_element, index):
        """Generate unique ID for Instagram post deduplication"""
        try:
            # Strategy 1: Get post URL
            try:
                post_link = post_element.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                if post_link and "/p/" in post_link:
                    return hash(post_link)
            except:
                pass
            
            # Strategy 2: Get image src
            try:
                img_element = post_element.find_element(By.CSS_SELECTOR, "img")
                img_src = img_element.get_attribute("src")
                if img_src:
                    return hash(img_src[:150])
            except:
                pass
            
            # Strategy 3: Get post text content
            try:
                content_elements = post_element.find_elements(By.CSS_SELECTOR, "span")
                content_text = " ".join([el.text for el in content_elements if el.text.strip()][:3])
                if content_text:
                    return hash(content_text[:100])
            except:
                pass
            
            # Final fallback
            return f"post_{index}_{int(time.time())}"
            
        except:
            return f"post_{index}_{int(time.time())}"

    def _open_post(self, post_element, index):
        """Open Instagram post dengan validasi URL yang ketat"""
        print(f"\n{'=' * 30}")
        print(f"   🔍 ATTEMPTING TO OPEN POST #{index}")
        print(f"{'=' * 30}")
        
        # Strategy 0: Pastikan halaman siap & tutup semua pop-up
        self._close_all_popups()
        time.sleep(1)
        
        # Strategy 1: Get valid post URL
        print("   🔗 Strategy 1: Getting valid post URL...")
        post_url = self._get_valid_post_url(post_element)
        
        if post_url:
            print(f"   ✅ Found valid post URL: {post_url}")
            self.driver.get(post_url)
            time.sleep(4)
            
            # Verifikasi kita di halaman post yang benar
            if not self._is_valid_post_url(self.driver.current_url):
                print("   ⚠️ Navigated to invalid page. Attempting recovery...")
                if self._handle_wrong_page():
                    print("   ✅ Successfully recovered to valid post page")
                else:
                    return False
            
            # Verifikasi modal terbuka
            try:
                WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div._a9zs, article"))
                )
                print("   ✅ Successfully opened post via direct URL")
                return True
            except:
                print("   ⚠️ Post URL loaded but content not detected")
                return False
        
        # Strategy 2: JavaScript click (bypass element intercept)
        try:
            print("\n   ⚡ Strategy 2: JavaScript click...")
            self.driver.execute_script("""
                var element = arguments[0];
                var event = new MouseEvent('click', {
                    'view': window,
                    'bubbles': true,
                    'cancelable': true
                });
                element.dispatchEvent(event);
            """, post_element)
            time.sleep(4)
            
            # Verifikasi kita di halaman post yang benar
            if not self._is_valid_post_url(self.driver.current_url):
                print("   ⚠️ JavaScript click led to invalid page. Attempting recovery...")
                if self._handle_wrong_page():
                    print("   ✅ Successfully recovered to valid post page")
                else:
                    return False
            
            # Verifikasi modal terbuka
            try:
                WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div._a9zs, article"))
                )
                print("   ✅ Successfully opened post via JavaScript click")
                return True
            except:
                print("   ⚠️ JavaScript click executed but modal not detected")
        except Exception as e:
            print(f"   ❌ Strategy 2 failed: {str(e)}")
        
        # Strategy 3: Action Chains click (simulate human click)
        try:
            print("\n   🤖 Strategy 3: Action Chains click...")
            
            # Scroll to element
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", post_element)
            time.sleep(1.5)
            
            # Move to element and click
            actions = ActionChains(self.driver)
            actions.move_to_element(post_element).pause(0.5).click().perform()
            time.sleep(4)
            
            # Verifikasi kita di halaman post yang benar
            if not self._is_valid_post_url(self.driver.current_url):
                print("   ⚠️ Action Chains click led to invalid page. Attempting recovery...")
                if self._handle_wrong_page():
                    print("   ✅ Successfully recovered to valid post page")
                else:
                    return False
            
            # Verifikasi modal terbuka
            try:
                WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div._a9zs, article"))
                )
                print("   ✅ Successfully opened post via Action Chains")
                return True
            except:
                print("   ⚠️ Action Chains click executed but modal not detected")
        except Exception as e:
            print(f"   ❌ Strategy 3 failed: {str(e)}")
        
        # Strategy 4: Find and click the first clickable ancestor
        try:
            print("\n   🔍 Strategy 4: Finding clickable ancestor...")
            
            # Cari semua ancestor yang clickable
            clickable_ancestors = post_element.find_elements(By.XPATH, "./ancestor::*[contains(@class, ' ') or contains(@href, '/')]")
            
            for ancestor in clickable_ancestors:
                try:
                    print(f"   🧭 Trying ancestor with tag: {ancestor.tag_name}")
                    ancestor.click()
                    time.sleep(4)
                    
                    # Verifikasi kita di halaman post yang benar
                    if not self._is_valid_post_url(self.driver.current_url):
                        print("   ⚠️ Ancestor click led to invalid page. Attempting recovery...")
                        if self._handle_wrong_page():
                            print("   ✅ Successfully recovered to valid post page")
                        else:
                            self.driver.back()
                            time.sleep(2)
                            continue
                    
                    # Verifikasi modal terbuka
                    try:
                        WebDriverWait(self.driver, 8).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div._a9zs, article"))
                        )
                        print("   ✅ Successfully opened post via clickable ancestor")
                        return True
                    except:
                        print("   ⚠️ Ancestor click failed, trying next...")
                        self.driver.back()
                        time.sleep(2)
                except:
                    continue
        except Exception as e:
            print(f"   ❌ Strategy 4 failed: {str(e)}")
        
        # Strategy 5: Screenshot untuk debugging
        try:
            print("\n   📸 Taking screenshot for debugging...")
            screenshot_name = f"post_open_failed_{index}_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_name)
            print(f"   ✅ Screenshot saved: {screenshot_name}")
        except:
            pass
        
        print("\n   ❌ ALL STRATEGIES FAILED TO OPEN POST")
        print(f"{'=' * 30}")
        return False

    def _extract_caption_from_modal(self):
        """Extract ONLY the main caption from Instagram modal post (with 'more' handling)"""
        print("   📝 Extracting MAIN caption only (with 'more' handling)...")
        
        # Pastikan kita berada di halaman yang benar
        if not self._is_valid_post_url(self.driver.current_url):
            print("   ⚠️ Not on valid post page - attempting to recover")
            if not self._handle_wrong_page():
                return ""
        
        # Strategy 1: Cari tombol "more" dan klik untuk menampilkan caption lengkap
        try:
            print("   🔍 Checking for 'more' button to expand caption...")
            more_button = None
            
            # Multiple strategies untuk menemukan tombol "more"
            more_selectors = [
                "div._a9zs > span > span > a",
                "div._a9zs > span > a",
                "div._a9zs a[role='button']",
                "div._a9zs a[href*='more']"
            ]
            
            for selector in more_selectors:
                try:
                    more_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    # Verifikasi apakah ini tombol "more"
                    if more_button.text.strip() == "more" or "more" in more_button.get_attribute("aria-label").lower():
                        print("   ✅ Found 'more' button")
                        more_button.click()
                        time.sleep(1.5)
                        break
                    more_button = None
                except:
                    continue
            
            if more_button:
                print("   ✅ Caption expanded with 'more' button")
        
        except Exception as e:
            print(f"   ⚠️ Error expanding caption: {str(e)}")
        
        # Strategy 2: Cari caption container
        try:
            print("   🎯 Strategy 1: Finding main caption container...")
            
            # Modern Instagram caption container
            caption_container = WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div._a9zs"))
            )
            
            # Get all span elements within the container
            caption_spans = caption_container.find_elements(By.CSS_SELECTOR, "span")
            
            # Find the main caption span (usually the first one with substantial content)
            for span in caption_spans:
                text = span.text.strip()
                if text and len(text) > 10 and not any(phrase in text for phrase in ["View all comments", "Lihat semua komentar", "See translation"]):
                    print(f"   ✅ Found main caption via strategy 1: {text[:50]}...")
                    return text
            
            print("   ⚠️ Strategy 1 found container but no valid caption")
        except Exception as e:
            print(f"   ❌ Strategy 1 failed: {str(e)}")
        
        # Strategy 3: JavaScript extraction with specific class targeting
        try:
            print("\n   🧪 Strategy 3: JavaScript caption extraction with class targeting...")
            
            caption = self.driver.execute_script("""
                // Find the main caption container
                let captionContainer = document.querySelector('div._a9zs, div.x78zum5');
                if (!captionContainer) return '';
                
                // Get all text elements in the container
                let textElements = captionContainer.querySelectorAll('span, p, div');
                let captionText = '';
                
                // Build caption text from all elements
                for (let i = 0; i < textElements.length; i++) {
                    let text = textElements[i].textContent.trim();
                    // Skip empty or short elements
                    if (text.length > 5) {
                        // Check if this is likely the main caption
                        if (captionText === '' && !text.includes('View all comments')) {
                            captionText = text;
                            break; // Take first substantial text as caption
                        }
                    }
                }
                
                // Clean caption text
                captionText = captionText.replace(/View all comments|Lihat semua komentar|See translation/g, '');
                captionText = captionText.replace(/\s+/g, ' ').trim();
                
                return captionText;
            """)
            
            if caption and len(caption) > 10:
                print(f"   ✅ Found caption via JavaScript strategy: {caption[:50]}...")
                return caption
            print("   ⚠️ JavaScript strategy returned empty or short caption")
        except Exception as e:
            print(f"   ❌ Strategy 3 failed: {str(e)}")
        
        print("   ❌ ALL CAPTION EXTRACTION STRATEGIES FAILED")
        return ""

    def _extract_username_from_modal(self):
        """Extract username from modal post"""
        username = "unknown"
        try:
            username_selectors = [
                "header h2 a",
                "header span._ap3a",
                "header span.x1lliihq",
                "header span.x193iq5w",
                "header div[role='button'] span"
            ]
            
            for selector in username_selectors:
                try:
                    username_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    username = username_element.text
                    if username and username != "unknown":
                        break
                except:
                    continue
        except:
            pass
        return username

    def _extract_timestamp_from_modal(self):
        """Extract timestamp from modal post"""
        timestamp = datetime.now().isoformat()
        try:
            time_element = self.driver.find_element(By.CSS_SELECTOR, "time")
            timestamp = time_element.get_attribute("datetime")
        except:
            pass
        return timestamp

    def _close_modal_if_open(self):
        """Close modal post if open"""
        try:
            close_btn = self.driver.find_element(By.CSS_SELECTOR, "[aria-label='Close'], [aria-label='Tutup']")
            close_btn.click()
            time.sleep(1.5)
            print("   ✅ Modal closed successfully")
            return True
        except:
            return False

    def _parse_instagram_post(self, post_element, post_index):
        """Parse Instagram post untuk hanya caption yang relevan"""
        print(f"   🔍 Parsing post {post_index} for caption only...")
        
        # Inisialisasi variabel
        caption = ""
        username = "unknown"
        timestamp = datetime.now().isoformat()
        post_url = ""
        
        try:
            # 1. Pastikan tidak ada pop-up yang menghalangi
            self._close_all_popups()
            
            # 2. Coba buka post dengan multiple strategies
            if not self._open_post(post_element, post_index):
                print("   ❌ Failed to open post")
                return None
            
            # 3. Pastikan kita berada di halaman post yang benar
            if not self._is_valid_post_url(self.driver.current_url):
                if not self._handle_wrong_page():
                    print("   ❌ Failed to return to valid post page")
                    return None
            
            # 4. Extract username
            username = self._extract_username_from_modal()
            
            # 5. Extract caption (HANYA CAPTION)
            caption = self._extract_caption_from_modal()
            
            # 6. Extract timestamp
            timestamp = self._extract_timestamp_from_modal()
            
            # 7. Get post URL
            try:
                post_url = self.driver.current_url
            except:
                pass
            
            # 8. Close modal
            self._close_modal_if_open()
            
            # 9. Validasi caption
            if not caption or len(caption) < 10:
                print(f"   ⚠️ Skipping post - caption too short: {caption[:30]}")
                return None
            
            print(f"   ✅ Caption extracted successfully!")
            print(f"      📝 Caption: {caption[:80]}...")
            print(f"      👥 Username: {username}")
            
            return {
                "platform": "instagram",
                "search_keyword": self.target_keyword,
                "username": username,
                "content": caption,
                "timestamp": timestamp,
                "likes": "N/A",  # Tidak dibutuhkan
                "comments": "N/A",  # Tidak dibutuhkan
                "post_url": post_url,
                "scraped_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"   🚨 Post parsing error: {str(e)}")
            self._close_modal_if_open()
            return None

    def _extract_posts(self):
        """Ekstrak post Instagram dengan penanganan halaman salah"""
        new_count = 0
        
        try:
            print("   🔍 Finding Instagram posts...")
            
            # Get posts list with retry mechanism
            posts = []
            max_attempts = 3
            attempt = 0
            
            while attempt < max_attempts and not posts:
                attempt += 1
                print(f"   🔄 Attempt {attempt}/{max_attempts} to find posts...")
                
                try:
                    # Multiple selectors for posts
                    post_selectors = [
                        "article", 
                        "div._aabd", 
                        "div._aagv", 
                        "a[href*='/p/']",
                        "div[class*='_aagv']"
                    ]
                    
                    for selector in post_selectors:
                        try:
                            print(f"   🎯 Trying selector: {selector}")
                            posts = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if posts:
                                print(f"   ✅ Found {len(posts)} posts using selector: {selector}")
                                break
                        except:
                            continue
                    
                    if not posts:
                        print("   ⚠️ No posts found with current selector, scrolling...")
                        self.driver.execute_script("window.scrollBy(0, window.innerHeight);")
                        time.sleep(2)
                
                except Exception as e:
                    print(f"   ❌ Error finding posts on attempt {attempt}: {str(e)}")
                    time.sleep(2)
            
            if not posts:
                print("   ❌ No posts found after all attempts")
                self.driver.save_screenshot("no_posts_found.png")
                return 0
            
            print(f"   📌 Found {len(posts)} potential posts to process")
            
            # Process each post
            for i, post in enumerate(posts):
                if len(self.posts_data) >= MAX_POSTS:
                    print(f"   ✅ Reached maximum posts limit: {MAX_POSTS}")
                    break
                
                print(f"   🔄 Processing post {i+1}/{len(posts)}")
                
                # Handle stale element
                try:
                    # Re-lookup element if needed
                    if i > 0:
                        try:
                            posts = self.driver.find_elements(By.CSS_SELECTOR, "article, div._aabd, div._aagv, a[href*='/p/']")
                            if i < len(posts):
                                post = posts[i]
                            else:
                                print(f"   ⚠️ Post index {i} out of range after refresh")
                                continue
                        except:
                            pass
                    
                    post_id = self._get_post_id(post, i)
                    if post_id in self.processed_posts:
                        print(f"   ℹ️ Skipping duplicate post (ID: {post_id})")
                        continue
                    
                    # Extract post data
                    post_data = self._parse_instagram_post(post, i+1)
                    if post_data and len(post_data['content']) > 10:
                        self.processed_posts.add(post_id)
                        self.posts_data.append(post_data)
                        new_count += 1
                        print(f"   ✅ [{len(self.posts_data)}/{MAX_POSTS}] Added post from @{post_data['username']}")
                        print(f"      Content: {post_data['content'][:60]}...")
                    
                except Exception as e:
                    print(f"   ❌ Error processing post {i+1}: {str(e)}")
                    self._close_modal_if_open()
                    continue
            
            return new_count
            
        except Exception as e:
            print(f"   ❌ Post extraction failed: {str(e)}")
            return 0

    def _save_results(self):
        """Simpan hasil Instagram scraping"""
        if not self.posts_data:
            print("❌ No Instagram posts to save")
            return False
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_keyword = self.target_keyword.replace(" ", "_").replace("/", "_").lower()
            filename = f"instagram_{safe_keyword}_{len(self.posts_data)}_posts_{timestamp}.{OUTPUT_FORMAT}"
            filepath = os.path.join(OUTPUT_FOLDER, filename)
            
            df = pd.DataFrame(self.posts_data)
            
            # Add metadata
            df['scraper_version'] = "1.5"
            df['extraction_date'] = datetime.now().isoformat()
            df['scroll_attempts'] = self.scroll_attempts
            df['search_strategy'] = self.current_search_strategy
            
            # Save
            if OUTPUT_FORMAT == "csv":
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
            else:
                df.to_json(filepath, orient='records', indent=2, ensure_ascii=False)
            
            print("\n✅ Instagram results saved successfully")
            print(f"   📁 Data file: {filepath}")
            print(f"   📊 Total posts: {len(self.posts_data)}")
            
            # Print sample data
            print("\n📋 Sample of extracted Instagram ")
            for i, post in enumerate(self.posts_data[:3], 1):
                print(f"   {i}. @{post['username']}: {post['content'][:70]}...")
            
            return True
            
        except Exception as e:
            print(f"❌ Instagram save failed: {str(e)}")
            return False

    def run(self):
        """Main execution flow dengan recovery mechanism"""
        print("🚀 Starting Instagram Scraper for 'program mbg'")
        print("=" * 60)
        print(f"🎯 Target: {MAX_POSTS} posts containing '{self.target_keyword}'")
        print("-" * 60)
        
        self.start_time = time.time()
        
        try:
            # Setup driver
            self.driver = self._setup_driver()
            
            # Load cookies and login
            if not self._load_cookies():
                print("❌ Instagram login failed. Cannot proceed with scraping.")
                return
            
            # Search for keyword
            if not self.search_keyword():
                print("❌ Instagram search failed. Cannot proceed with scraping.")
                self.driver.save_screenshot("search_failed_final.png")
                return
            
            # Main extraction loop
            total_attempts = 0
            max_attempts = 3
            
            while total_attempts < max_attempts and len(self.posts_data) < MAX_POSTS:
                total_attempts += 1
                print(f"\n{'=' * 60}")
                print(f"   🔄 EXTRACTION ATTEMPT #{total_attempts}/{max_attempts}")
                print(f"{'=' * 60}")
                
                # Scroll and extract posts
                self._smart_scroll_until_target()
                
                # Handle redirects and popups
                self._handle_instagram_redirects()
                self._close_all_popups()
                
                # If we got enough posts, break
                if len(self.posts_data) >= MAX_POSTS:
                    break
                
                # If no posts were found, try to recover
                if not self.posts_data and total_attempts < max_attempts:
                    print("   ⚠️ No posts extracted. Attempting recovery...")
                    self.driver.refresh()
                    time.sleep(5)
                    self._close_all_popups()
            
            # Save results
            if self.posts_data:
                self._save_results()
            else:
                print(f"❌ No valid Instagram posts containing '{self.target_keyword}' were found after {max_attempts} attempts.")
                self.driver.save_screenshot("no_valid_posts_final.png")
            
        except Exception as e:
            print(f"❌ Critical error in Instagram scraper: {str(e)}")
            import traceback
            traceback.print_exc()
            if self.driver:
                self.driver.save_screenshot("instagram_crash_final.png")
        finally:
            try:
                if self.driver:
                    print("\n\n{'=' * 60}")
                    print("   📊 FINAL SCRAPER STATISTICS")
                    print(f"   Total posts extracted: {len(self.posts_data)}")
                    print(f"   Session duration: {time.time() - self.start_time:.1f} seconds")
                    print(f"   Success rate: {len(self.posts_data)/MAX_POSTS*100:.1f}%")
                    print("{'=' * 60}\n")
                    
                    print("\n🔌 Closing Instagram browser...")
                    self.driver.quit()
                    print("✅ Instagram browser closed successfully")
            except:
                pass

if __name__ == "__main__":
    scraper = InstagramScraper()
    scraper.run()