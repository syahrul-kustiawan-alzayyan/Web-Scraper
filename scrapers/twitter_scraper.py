from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
    TWITTER_COOKIES,
    OUTPUT_FOLDER,
    OUTPUT_FORMAT,
    MAX_SCROLL_ATTEMPTS,
    SCROLL_RECOVERY_DELAY,
    MIN_DELAY_BETWEEN_SCROLLS,
    MAX_DELAY_BETWEEN_SCROLLS,
    SESSION_RESTART_THRESHOLD,
    MAX_SESSION_DURATION,
    KEYWORDS,
    INDO_REGIONS_FILE
)
class ProductionTwitterScraper:
    def __init__(self):
        self.driver = None
        self.posts_data = []
        self.processed_posts = set()
        self.start_time = None
        self.scroll_attempts = 0
        self.session_posts = 0
        self.target_keywords = KEYWORDS if KEYWORDS else ["prabowo makan"]
        self.session_start_time = None
        self.total_posts_found = 0
        self.keyword_stats = {}
        self.unlimited_mode = True
        self.last_successful_keyword = None
        self.last_successful_post_hash = None
        self.indonesian_regions = self._load_indonesian_regions()  # Load dari file JSON

    def _load_indonesian_regions(self):
        """Load daftar provinsi dan kabupaten/kota Indonesia dari file JSON"""
        try:
            if not os.path.exists(INDO_REGIONS_FILE):
                print(f"[WARNING] Indonesian regions file not found at: {INDO_REGIONS_FILE}")
                return {}
            
            with open(INDO_REGIONS_FILE, 'r', encoding='utf-8') as f:
                regions_data = json.load(f)
                print(f"[INFO] Successfully loaded Indonesian regions data: {len(regions_data)} provinces")
                return regions_data
        except Exception as e:
            print(f"[ERROR] Failed to load Indonesian regions: {str(e)}")
            return {}

    def _setup_driver(self):
        """Setup Chrome driver dengan opsi untuk mengurangi error GPU"""
        options = Options()
        
        # Essential production options dengan GPU error reduction
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-webgl")
        options.add_argument("--disable-3d-apis")
        options.add_argument("--disable-gpu-compositing")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-infobars")
        
        # Anti-detection settings
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-automation")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Clean user agent
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        if BROWSER_HEADLESS:
            options.add_argument("--headless=new")
        
        service = Service(SELENIUM_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
        
        # Extra anti-detection script
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
        
        return driver

    def _load_cookies(self):
        """Load cookies dengan validation untuk production"""
        if not TWITTER_COOKIES:
            print("[ERROR] No Twitter cookies found. Scraper cannot proceed.")
            return False
            
        try:
            self.driver.get("https://twitter.com")
            time.sleep(PAGE_LOAD_DELAY)
            
            # Clear existing cookies first
            self.driver.delete_all_cookies()
            
            # Add cookies with domain fix
            valid_cookies = 0
            for cookie in TWITTER_COOKIES:
                try:
                    cookie = cookie.copy()
                    if 'domain' in cookie:
                        cookie['domain'] = cookie['domain'].replace('.twitter.com', 'twitter.com')
                    
                    if 'name' not in cookie or 'value' not in cookie:
                        continue
                    
                    self.driver.add_cookie(cookie)
                    valid_cookies += 1
                except:
                    continue
            
            # Refresh to apply cookies
            self.driver.refresh()
            time.sleep(PAGE_LOAD_DELAY * 2)
            
            # Verify login
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='SideNav_NewTweet_Button'], [data-testid='tweetButtonInline']"))
                )
                print("✅ Twitter login successful")
                return True
            except:
                print("[ERROR] Login verification failed. Session may be invalid.")
                return False
                
        except:
            return False

    def _clear_browser_state(self):
        """Bersihkan semua state browser sebelum ganti keyword"""
        try:
            print("   🧹 Clearing browser cache and state...")
            
            # Hapus semua cookies
            self.driver.delete_all_cookies()
            
            # Clear local storage dan session storage
            self.driver.execute_script("window.localStorage.clear();")
            self.driver.execute_script("window.sessionStorage.clear();")
            
            # Clear cache
            self.driver.execute_script("caches.keys().then(function(names) {for (let name of names) caches.delete(name);});")
            
            # Navigate ke halaman kosong untuk memastikan cache bersih
            self.driver.get("about:blank")
            time.sleep(2)
            
            print("   ✅ Browser state cleared successfully")
            return True
        except Exception as e:
            print(f"   ❌ Failed to clear browser state: {str(e)}")
            return False

    def _handle_error_and_retry(self, keyword, last_successful_post=None):
        """Handle error dengan login ulang dan retry dari post terakhir"""
        print(f"\n⚠️ Error detected for keyword '{keyword}'. Attempting recovery...")
        
        try:
            # Simpan data yang sudah berhasil dikumpulkan
            if self.posts_data:  # FIX: posts_ -> posts_data
                print("   💾 Saving partial results before recovery...")
                self._save_partial_results(f"RECOVERY_{keyword.replace(' ', '_')}")
            
            # Tutup browser yang bermasalah
            if self.driver:
                print("   🔌 Closing current browser session...")
                self.driver.quit()
                time.sleep(5)
            
            # Setup browser baru
            print("   🔄 Setting up new browser session...")
            self.driver = self._setup_driver()
            
            # Login ulang
            print("   🔑 Re-authenticating with Twitter...")
            if not self._load_cookies():
                print("❌ Failed to re-login. Recovery aborted.")
                return False
            
            # Cari keyword lagi
            print(f"   🔍 Restarting search for keyword: '{keyword}'")
            if not self.search_keyword(keyword):
                print("❌ Failed to search keyword after recovery. Recovery aborted.")
                return False
            
            # Jika ada post terakhir yang berhasil, coba mulai dari sana
            if last_successful_post:
                print("   🎯 Attempting to resume from last successful content...")
                # Di sini bisa ditambahkan logika untuk mencari konten terakhir
                # Untuk saat ini, kita mulai dari awal dengan pengecekan duplikat
            
            print("✅ Recovery successful. Continuing scraping.")
            return True
            
        except Exception as e:
            print(f"❌ Recovery failed: {str(e)}")
            return False

    def search_keyword(self, keyword):
        """Search dengan keyword spesifik (TANPA FILTER TANGGAL)"""
        try:
            # URL encode keyword
            encoded_keyword = urllib.parse.quote(keyword)
            
            # Production search URL TANPA parameter waktu
            search_url = f"https://twitter.com/search?q={encoded_keyword}&src=typed_query&f=live"
            
            print(f"   🌐 Navigating to search URL...")
            self.driver.get(search_url)
            time.sleep(PAGE_LOAD_DELAY * 2)
            
            # Handle cookie banner
            self._handle_cookie_banner()
            
            # Apply latest filter
            self._apply_latest_filter()
            
            # Verifikasi hasil pencarian
            if self._has_search_results():
                print(f"✅ Search results loaded for keyword: '{keyword}'")
                return True
            else:
                print(f"❌ No search results found for keyword: '{keyword}'")
                return False
                
        except Exception as e:
            print(f"❌ Search failed for keyword '{keyword}': {str(e)}")
            return False

    def _handle_cookie_banner(self):
        """Handle cookie banner untuk production"""
        try:
            accept_selectors = [
                "//button[contains(text(),'Accept') or contains(text(),'accept') or contains(text(),'I agree')]",
                "[data-testid='accept']",
                "[aria-label*='accept']"
            ]
            
            for selector in accept_selectors:
                try:
                    if selector.startswith("//"):
                        element = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        element = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    element.click()
                    time.sleep(2)
                    return
                except:
                    continue
        except:
            pass

    def _apply_latest_filter(self):
        """Apply 'Latest' filter untuk konten terbaru"""
        try:
            # Click filter button
            filter_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='searchFilterButton']"))
            )
            filter_btn.click()
            time.sleep(2)
            
            # Click "Latest" option
            latest_option = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'Latest') or contains(text(),'Terbaru')]"))
            )
            latest_option.click()
            time.sleep(3)
            
            return True
            
        except:
            return False

    def _has_search_results(self):
        """Periksa apakah pencarian menghasilkan hasil"""
        try:
            # Cek indikator "No results"
            no_results_selectors = [
                "//div[contains(text(),'No results') or contains(text(),'Tidak ada hasil')]",
                "[data-testid='emptyState']",
                ".css-1dbjc4n.r-1awozwy.r-18u37iz.r-dnmrzs"
            ]
            
            for selector in no_results_selectors:
                try:
                    if selector.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        for el in elements:
                            if el.is_displayed() and el.text.strip() != "":
                                return False
                except:
                    continue
            
            # Cek apakah ada tweet yang terlihat
            tweet_selectors = [
                "article[data-testid='tweet']",
                "[data-testid='tweet']",
                "div[aria-labelledby^='id__']",
                "div[data-testid='tweetText']",
                "section > div > div"
            ]
            
            for selector in tweet_selectors:
                try:
                    tweets = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    visible_tweets = [t for t in tweets if t.is_displayed()]
                    if visible_tweets:
                        return True
                except:
                    continue
            
            return False
            
        except:
            return False

    def _display_progress(self, keyword, posts_this_keyword, elapsed_time):
        """Tampilkan progres scraping dengan format yang jelas"""
        total_posts = len(self.posts_data)
        avg_collection_rate = total_posts / max(1, elapsed_time)
        progress_percent = min(100, (self.scroll_attempts / MAX_SCROLL_ATTEMPTS) * 100)
        
        print(f"\n{'=' * 60}")
        print(f"📊 PROGRESS REPORT - Keyword: '{keyword}'")
        print(f"{'=' * 60}")
        print(f"   📌 Posts from this keyword: {posts_this_keyword:,}")
        print(f"   📌 Total posts collected: {total_posts:,}")
        print(f"   ⏱️  Elapsed time: {elapsed_time:.1f} seconds")
        print(f"   📈 Collection rate: {avg_collection_rate:.2f} posts/second")
        print(f"   🔄 Scroll attempts: {self.scroll_attempts}/{MAX_SCROLL_ATTEMPTS} ({progress_percent:.1f}%)")
        print(f"   💾 Last save: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'=' * 60}")

    def _smart_scroll_until_target(self, keyword):
        """Scrolling cerdas dengan progres tracking dan recovery"""
        keyword_start_time = time.time()
        last_post_count = 0
        no_new_content_count = 0
        keyword_posts = 0
        last_save_time = time.time()
        last_progress_time = time.time()
        PROGRESS_INTERVAL = 15  # Update progres setiap 15 detik
        ERROR_THRESHOLD = 3  # Jumlah error sebelum recovery
        error_count = 0
        last_successful_post = None
        
        while (self.scroll_attempts < MAX_SCROLL_ATTEMPTS and
               time.time() - keyword_start_time < MAX_SESSION_DURATION / len(self.target_keywords)):
            
            current_time = time.time()
            
            # Tampilkan progres secara berkala
            if current_time - last_progress_time > PROGRESS_INTERVAL:
                self._display_progress(keyword, keyword_posts, current_time - keyword_start_time)
                last_progress_time = current_time
            
            self.scroll_attempts += 1
            elapsed_time = current_time - keyword_start_time
            
            try:
                # Scroll down in increments
                self._incremental_scroll()
                
                # Wait with random delay
                scroll_delay = random.uniform(MIN_DELAY_BETWEEN_SCROLLS, MAX_DELAY_BETWEEN_SCROLLS)
                time.sleep(scroll_delay)
                
                # Extract new posts
                new_posts = self._extract_new_posts(keyword)
                keyword_posts += new_posts
                
                if new_posts > 0:
                    error_count = 0
                    last_successful_post = self.posts_data[-1] if self.posts_data else None  # FIX: posts_ -> posts_data
                
                # Check for no new content
                current_count = len(self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']"))
                if current_count == last_post_count:
                    no_new_content_count += 1
                    
                    if no_new_content_count >= 10:
                        print("   🛑 No new content after 10 attempts. Moving to next keyword.")
                        break
                else:
                    no_new_content_count = 0
                    last_post_count = current_count
                
                # Periodic save every 5 minutes
                if current_time - last_save_time > 300:
                    print("   💾 Periodic save triggered...")
                    self._save_partial_results(f"UNLIMITED_{keyword.replace(' ', '_')}")
                    last_save_time = current_time
                
                # Session restart if needed
                if len(self.posts_data) >= SESSION_RESTART_THRESHOLD:
                    print(f"   🔁 Session restart threshold reached ({SESSION_RESTART_THRESHOLD} posts). Saving progress...")
                    self._save_partial_results(f"UNLIMITED_{keyword.replace(' ', '_')}")
                    self.driver.quit()
                    time.sleep(8)
                    self.driver = self._setup_driver()
                    self._load_cookies()
                    self.search_keyword(keyword)
                    last_post_count = 0
            
            except Exception as e:
                error_count += 1
                print(f"   ❌ Scroll attempt {self.scroll_attempts} failed: {str(e)}")
                
                # Jika error berturut-turut, coba recovery
                if error_count >= ERROR_THRESHOLD:
                    print(f"   🔥 {ERROR_THRESHOLD} consecutive errors detected. Attempting recovery...")
                    
                    if self._handle_error_and_retry(keyword, last_successful_post):
                        print("   ✅ Recovery successful. Continuing...")
                        error_count = 0
                    else:
                        print("   ❌ Recovery failed. Skipping this keyword.")
                        break
                
                time.sleep(SCROLL_RECOVERY_DELAY)
        
        # Update statistics
        if keyword not in self.keyword_stats:
            self.keyword_stats[keyword] = 0
        self.keyword_stats[keyword] += keyword_posts
        
        # Final progress display
        self._display_progress(keyword, keyword_posts, time.time() - keyword_start_time)
        
        return keyword_posts

    def _incremental_scroll(self):
        """Scroll bertahap untuk menghindari deteksi bot"""
        # Scroll in small increments
        for i in range(3):
            scroll_height = (i + 1) * (self.driver.execute_script("return document.body.scrollHeight") // 3)
            self.driver.execute_script(f"window.scrollTo(0, {scroll_height});")
            time.sleep(0.5)
        
        # Final scroll to bottom
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
    def _extract_indonesian_location(self, text):
        """
        Ekstrak lokasi kabupaten/kota atau provinsi Indonesia dari teks
        Menggunakan data dari file JSON yang berisi struktur provinsi -> kabupaten/kota
        """
        if not text or not self.indonesian_regions:
            return "unknown"
        
        text_lower = text.lower().replace('.', ' ').replace(',', ' ').replace(';', ' ').replace(':', ' ')
        found_locations = []
        
        # 1. Cari kabupaten/kota terlebih dahulu (prioritas tertinggi)
        for province, cities in self.indonesian_regions.items():
            for city in cities:
                city_lower = city.lower()
                # Cari kecocokan persis atau sebagai bagian dari teks
                if city_lower in text_lower or text_lower in city_lower:
                    # Prioritaskan lokasi yang lebih spesifik
                    if "kabupaten" in city_lower or "kota" in city_lower or "kab." in text_lower or "kota" in text_lower:
                        found_locations.insert(0, city)  # Prioritas tertinggi
                    else:
                        found_locations.append(city)
        
        # 2. Jika tidak ditemukan kabupaten/kota, cari provinsi
        if not found_locations:
            for province in self.indonesian_regions.keys():
                province_lower = province.lower()
                if province_lower in text_lower or text_lower in province_lower:
                    found_locations.append(province)
        
        # 3. Cari pola umum lokasi
        if not found_locations:
            location_patterns = [
                r'kabupaten\s+([a-z\s]+)',
                r'kota\s+([a-z\s]+)',
                r'di\s+([a-z\s]+)',
                r'provinsi\s+([a-z\s]+)',
                r'([a-z\s]+)\s+kabupaten',
                r'([a-z\s]+)\s+kota',
                r'([a-z\s]+)\s+provinsi',
                r'([a-z\s]+)\s+indonesia'
            ]
            
            for pattern in location_patterns:
                matches = re.findall(pattern, text_lower)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match else ""
                    match = str(match).strip()
                    if match and len(match) > 2:  # Minimal 3 karakter
                        # Cari kecocokan dengan daftar lokasi
                        for province, cities in self.indonesian_regions.items():
                            # Cek apakah match cocok dengan nama kota
                            for city in cities:
                                city_lower = city.lower()
                                if match in city_lower or city_lower in match:
                                    found_locations.append(city)
                                    break
                            else:
                                # Cek apakah match cocok dengan nama provinsi
                                province_lower = province.lower()
                                if match in province_lower or province_lower in match:
                                    found_locations.append(province)
                            if found_locations:
                                break
        
        # 4. Return hasil dengan prioritas
        if found_locations:
            # 1. Prioritaskan lokasi dengan prefix "kabupaten" atau "kota"
            for loc in found_locations:
                if "kabupaten" in loc.lower() or "kota" in loc.lower() or "kab." in loc.lower() or "kotamadya" in loc.lower():
                    return loc
            
            # 2. Prioritaskan lokasi kabupaten/kota (bukan provinsi)
            for loc in found_locations:
                for province, cities in self.indonesian_regions.items():
                    if loc in cities:
                        return loc
            
            # 3. Jika tidak ada yang spesifik, kembalikan lokasi pertama
            return found_locations[0]
        
        return "unknown"

    def _extract_new_posts(self, keyword):
        """Ekstrak post baru dengan deduplication dan tagging keyword"""
        try:
            # Multiple strategies untuk menemukan posts
            post_selectors = [
                "article[data-testid='tweet']",
                "[data-testid='tweet']",
                "div[aria-labelledby^='id__']",
                "div[data-testid='tweetText']",
                "section > div > div"
            ]
            
            posts = []
            for selector in post_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        posts = elements
                        break
                except:
                    continue
            
            if not posts:
                return 0
            
            new_count = 0
            for post in posts:
                post_hash = self._get_post_hash(post)
                if post_hash in self.processed_posts:
                    continue
                
                post_data = self._parse_single_post(post, keyword)
                if post_data:  # FIX: post_ -> post_data
                    self.processed_posts.add(post_hash)
                    self.posts_data.append(post_data)
                    new_count += 1
            
            return new_count
            
        except Exception as e:
            print(f"   ❌ Extraction error: {str(e)}")
            return 0

    def _get_post_hash(self, post):
        """Generate unique hash untuk deduplication"""
        try:
            content_hash = post.get_attribute('outerHTML')[:200]
            return hash(content_hash)
        except:
            return hash(time.time())

    def _parse_single_post(self, post, keyword):
        """Parse single post dengan ekstraksi lokasi dari file JSON"""
        try:
            # Username
            username = "unknown"
            try:
                username_element = post.find_element(By.CSS_SELECTOR, "[data-testid='User-Name'] span:last-child")
                username = username_element.text
            except:
                try:
                    username_element = post.find_element(By.CSS_SELECTOR, "[data-testid='UserName'] span")
                    username = username_element.text
                except:
                    pass
            
            # Content
            content = ""
            try:
                content_element = post.find_element(By.CSS_SELECTOR, "[data-testid='tweetText']")
                content = content_element.text
            except:
                try:
                    content_elements = post.find_elements(By.CSS_SELECTOR, "span")
                    content = " ".join([el.text for el in content_elements if len(el.text.strip()) > 3][:5])
                except:
                    pass
            
            # Skip if content too short
            if not content or len(content) < 5:
                return None
            
            # **EKSTRAKSI LOKASI** menggunakan data dari file JSON
            location = self._extract_indonesian_location(content)
            
            # Timestamp
            timestamp = datetime.now().isoformat()
            try:
                time_element = post.find_element(By.CSS_SELECTOR, "time")
                timestamp = time_element.get_attribute("datetime")
            except:
                try:
                    time_element = post.find_element(By.CSS_SELECTOR, "[aria-label]")
                    time_text = time_element.get_attribute("aria-label")
                    timestamp = self._parse_aria_timestamp(time_text)
                except:
                    pass
            
            # Engagement
            likes = "0"
            try:
                like_element = post.find_element(By.CSS_SELECTOR, "[data-testid*='like']")
                likes = like_element.text or "0"
            except:
                pass
            
            retweets = "0"
            try:
                retweet_element = post.find_element(By.CSS_SELECTOR, "[data-testid*='retweet']")
                retweets = retweet_element.text or "0"
            except:
                pass
            
            # Relevancy check
            if not self._is_content_relevant(content, keyword):
                return None
            
            return {
                "platform": "twitter",
                "search_keyword": keyword,
                "username": username,
                "content": content,
                "location": location,  # Field lokasi dari file JSON
                "timestamp": timestamp,
                "likes": likes,
                "retweets": retweets,
                "scraped_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"   🚨 Parsing error: {str(e)}")
            return None

    def _parse_aria_timestamp(self, aria_label):
        """Parse timestamp from aria-label"""
        try:
            # Extract date part
            date_match = re.search(r'(\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2} [A-Za-z]+,? \d{4})', aria_label)
            if date_match:
                date_str = date_match.group(1).replace(',', '').strip()
                try:
                    # Try common date formats
                    for fmt in ["%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%b %d %Y", "%B %d %Y"]:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt)
                            return parsed_date.isoformat()
                        except:
                            continue
                except:
                    pass
            return datetime.now().isoformat()
        except:
            return datetime.now().isoformat()

    def _is_content_relevant(self, content, keyword):
        """Check if content is relevant to the keyword"""
        if not content or not keyword:
            return True
        
        content_lower = content.lower()
        keyword_lower = keyword.lower()
        
        # Check for exact keyword match
        if keyword_lower in content_lower:
            return True
        
        # Check for related terms based on keyword
        related_terms = {
            "makan bergizi gratis": ["mbg", "program", "sekolah", "siswa", "prabowo"],
            "prabowo makan": ["mbg", "program", "gratis", "sekolah", "kemendikbud"],
            "mbg sekolah": ["makan bergizi", "gratis", "prabowo", "siswa", "pendidikan"],
            "program makan siswa": ["mbg", "gratis", "sekolah", "prabowo", "kemendikbud"]
        }
        
        # Get related terms for this keyword
        terms = related_terms.get(keyword_lower, [])
        terms.append(keyword_lower.split()[0])  # Add first word of keyword
        
        # Check if any related term is in content
        for term in terms:
            if term in content_lower:
                return True
        
        return False

    def _save_partial_results(self, prefix="UNLIMITED"):
        """Simpan hasil sementara untuk session restart"""
        if not self.posts_data:  # FIX: posts_ -> posts_data
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{len(self.posts_data)}_posts_{timestamp}.{OUTPUT_FORMAT}"
            filepath = os.path.join(OUTPUT_FOLDER, filename)
            
            df = pd.DataFrame(self.posts_data)
            
            if OUTPUT_FORMAT == "csv":
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
            else:
                df.to_json(filepath, orient='records', indent=2, ensure_ascii=False)
            
            return filepath
            
        except Exception as e:
            print(f"   ❌ Partial save failed: {str(e)}")
            return None

    def save_final_results(self):
        """Simpan hasil akhir dengan metadata lokasi yang lengkap"""
        if not self.posts_data:
            print("❌ No data to save")
            return False
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"UNLIMITED_{len(self.posts_data)}_posts_{timestamp}.{OUTPUT_FORMAT}"
            filepath = os.path.join(OUTPUT_FOLDER, filename)
            
            df = pd.DataFrame(self.posts_data)
            
            # Add metadata columns
            df['scraper_version'] = "3.3 (JSON LOCATION DATA)"
            df['extraction_date'] = datetime.now().isoformat()
            df['session_duration'] = f"{time.time() - self.start_time:.1f} seconds"
            df['total_keywords'] = len(self.target_keywords)
            df['keywords_used'] = ", ".join(self.target_keywords)
            df['total_scroll_attempts'] = self.scroll_attempts
            df['average_collection_rate'] = f"{len(self.posts_data)/max(1, (time.time() - self.start_time)):.2f} posts/second"
            
            # Save
            if OUTPUT_FORMAT == "csv":
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
            else:
                df.to_json(filepath, orient='records', indent=2, ensure_ascii=False)
            
            # Save metadata
            location_stats = {}
            for post in self.posts_data:
                loc = post.get('location', 'unknown')
                if loc != 'unknown':
                    location_stats[loc] = location_stats.get(loc, 0) + 1
            
            metadata = {
                "scraper_info": {
                    "name": "Twitter Scraper with JSON Location Data",
                    "version": "3.3",
                    "mode": "UNLIMITED",
                    "actual_posts": len(self.posts_data),
                    "keywords_used": self.target_keywords,
                    "total_keywords": len(self.target_keywords),
                    "extraction_date": datetime.now().isoformat(),
                    "session_duration": f"{time.time() - self.start_time:.1f} seconds",
                    "total_scroll_attempts": self.scroll_attempts,
                    "average_collection_rate": f"{len(self.posts_data)/max(1, (time.time() - self.start_time)):.2f} posts/second",
                    "output_file": filepath
                },
                "location_statistics": {
                    "total_posts_with_location": len([p for p in self.posts_data if p.get('location', 'unknown') != 'unknown']),
                    "location_distribution": location_stats,
                    "provinces_mentioned": list(set([province for province in self.indonesian_regions.keys() if any(province.lower() in post.get('location', '').lower() for post in self.posts_data)])),
                    "cities_mentioned": list(set([city for post in self.posts_data for province, cities in self.indonesian_regions.items() for city in cities if city.lower() in post.get('location', '').lower()]))
                },
                "post_statistics": {
                    "unique_authors": len(set([p.get('username', 'unknown') for p in self.posts_data])),
                    "avg_content_length": sum(len(p.get('content', '')) for p in self.posts_data) / max(1, len(self.posts_data)),
                    "posts_per_keyword": self.keyword_stats,
                    "total_posts": len(self.posts_data)
                }
            }
            
            metadata_file = os.path.join(OUTPUT_FOLDER, f"UNLIMITED_metadata_{timestamp}.json")
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            print("\n✅ LOCATION STATISTICS:")
            print(f"   📍 Total posts with location: {metadata['location_statistics']['total_posts_with_location']}/{len(self.posts_data)}")
            print(f"   🏙️  Unique locations found: {len(metadata['location_statistics']['location_distribution'])}")
            print(f"   🗺️  Provinces mentioned: {len(metadata['location_statistics']['provinces_mentioned'])}")
            print(f"   🏘️  Cities/regencies mentioned: {len(metadata['location_statistics']['cities_mentioned'])}")
            
            return True
            
        except Exception as e:
            print(f"❌ Final save failed: {str(e)}")
            return False

    def run(self):
        """Main production execution flow untuk unlimited multi keyword"""
        print("🚀 Starting UNLIMITED Twitter Scraper for MULTIPLE KEYWORDS")
        print("=" * 70)
        
        self.start_time = time.time()
        
        try:
            # Initialize driver
            self.driver = self._setup_driver()
            
            # Load cookies and login
            if not self._load_cookies():
                print("❌ Login failed. Cannot proceed with scraping.")
                return self.keyword_stats
            
            # Process each keyword
            for i, keyword in enumerate(self.target_keywords, 1):
                print(f"\n{'=' * 60}")
                print(f"🎯 PROCESSING KEYWORD {i}/{len(self.target_keywords)}: '{keyword}'")
                print(f"{'=' * 60}")
                
                if self.search_keyword(keyword):
                    self._smart_scroll_until_target(keyword)
                else:
                    print(f"❌ Failed to process keyword '{keyword}'")
                
                # Clear browser state before next keyword
                if i < len(self.target_keywords):
                    print(f"\n{'=' * 50}")
                    print("🧹 CLEARING BROWSER CACHE BEFORE NEXT KEYWORD")
                    print(f"{'=' * 50}")
                    self._clear_browser_state()
                    
                    # Delay between keywords
                    delay = random.uniform(8, 15)
                    print(f"⏳ Waiting {delay:.1f} seconds before next keyword...")
                    time.sleep(delay)
            
            # Save final results
            print("\n\n" + "=" * 60)
            print("🏁 SCRAPING SESSION COMPLETED")
            print("=" * 60)
            
            if self.posts_data:  # FIX: posts_ -> posts_data
                self.save_final_results()
                print(f"✅ Total posts collected: {len(self.posts_data):,}")
                print(f"✅ Total keywords processed: {len(self.target_keywords)}")
            else:
                print("❌ No posts were collected. Check your cookies and connection.")
            
            return self.keyword_stats
            
        except Exception as e:
            print(f"❌ Critical error in scraper: {str(e)}")
            
            # Attempt one recovery
            print("\n🔄 Attempting one-time recovery...")
            if self._handle_error_and_retry("final_recovery"):
                print("✅ Recovery successful. Continuing...")
                return self.keyword_stats
            else:
                print("❌ Final recovery failed. Shutting down.")
                return self.keyword_stats
        finally:
            try:
                if self.driver:
                    print("\n🔌 Closing browser...")
                    self.driver.quit()
                    print("✅ Browser closed successfully")
            except:
                pass

if __name__ == "__main__":
    scraper = ProductionTwitterScraper()
    scraper.run()