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
    MAX_SESSION_DURATION
)

class ProductionTwitterScraper:
    def __init__(self):
        self.driver = None
        self.posts_data = []
        self.processed_posts = set()
        self.start_time = None
        self.scroll_attempts = 0
        self.session_posts = 0

    def _setup_driver(self):
        """Setup Chrome driver untuk production dengan anti-detection"""
        print("🔧 Setting up production Chrome driver...")
        options = Options()
        
        # Essential production options
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        
        # Anti-detection settings
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-automation")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # User agent realistis
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
        """)
        
        print("✅ Production Chrome driver initialized")
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
                except Exception as e:
                    continue
            
            print(f"   ✅ Added {valid_cookies} valid cookies")
            
            # Refresh to apply cookies
            self.driver.refresh()
            time.sleep(PAGE_LOAD_DELAY * 2)
            
            # Verify login
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='SideNav_NewTweet_Button'], [data-testid='tweetButtonInline']"))
                )
                print("✅ [SUCCESS] Twitter login successful")
                return True
            except:
                print("[ERROR] Login verification failed. Session may be invalid.")
                self.driver.save_screenshot("login_verification_failed.png")
                return False
                
        except Exception as e:
            print(f"[ERROR] Cookie loading failed: {e}")
            return False

    def search_mbg(self):
        """Search MBG tanpa filter waktu"""
        print("\n🔍 Starting production search for 'MBG' (All Time)")
        
        try:
            # Production search URL tanpa parameter waktu
            search_url = (
                "https://twitter.com/search?q=MBG&src=typed_query"
                "&f=live"  # Hanya konten live/terbaru
            )
            
            print(f"   Navigating to: {search_url}")
            self.driver.get(search_url)
            time.sleep(PAGE_LOAD_DELAY * 2)
            
            # Handle cookie banner
            self._handle_cookie_banner()
            
            # Apply latest filter
            self._apply_latest_filter()
            
            print("✅ Production search page loaded successfully")
            return True
            
        except Exception as e:
            print(f"❌ Production search failed: {e}")
            self.driver.save_screenshot("production_search_failed.png")
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
                    print("   ✅ Accepted cookie consent")
                    return
                except:
                    continue
            print("   ℹ️ No cookie banner found")
        except:
            pass

    def _apply_latest_filter(self):
        """Apply 'Latest' filter untuk konten terbaru"""
        try:
            print("   Applying 'Latest' filter...")
            
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
            
            print("   ✅ 'Latest' filter applied successfully")
            return True
            
        except Exception as e:
            print(f"   ⚠️ Latest filter application skipped: {e}")
            return False

    def _smart_scroll_until_target(self):
        """Scrolling cerdas hingga mencapai target 1000 data"""
        print("\n🔄 Starting smart scrolling for 1000 MBG posts...")
        print("=" * 60)
        
        self.start_time = time.time()
        last_post_count = 0
        no_new_content_count = 0
        
        while (self.scroll_attempts < MAX_SCROLL_ATTEMPTS and 
               len(self.posts_data) < MAX_POSTS and
               time.time() - self.start_time < MAX_SESSION_DURATION):
            
            self.scroll_attempts += 1
            elapsed_time = time.time() - self.start_time
            print(f"\n📈 Scroll Attempt {self.scroll_attempts}/{MAX_SCROLL_ATTEMPTS} | Elapsed: {elapsed_time:.1f}s")
            print(f"   Current posts: {len(self.posts_data)}/{MAX_POSTS}")
            
            try:
                # Scroll down in increments
                self._incremental_scroll()
                
                # Wait with random delay
                scroll_delay = random.uniform(MIN_DELAY_BETWEEN_SCROLLS, MAX_DELAY_BETWEEN_SCROLLS)
                print(f"   ⏳ Waiting {scroll_delay:.1f}s for content to load...")
                time.sleep(scroll_delay)
                
                # Extract new posts
                new_posts = self._extract_new_posts()
                print(f"   📊 This scroll: {new_posts} new posts | Total: {len(self.posts_data)}")
                
                # Check for no new content
                current_count = len(self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']"))
                if current_count == last_post_count:
                    no_new_content_count += 1
                    print(f"   ⚠️ No new content ({no_new_content_count}/3)")
                    
                    if no_new_content_count >= 3:
                        print("   🛑 Stopping scroll - no new content after 3 attempts")
                        break
                else:
                    no_new_content_count = 0
                    last_post_count = current_count
                
                # Session restart if needed
                if len(self.posts_data) >= SESSION_RESTART_THRESHOLD:
                    print("   🔁 Session restart threshold reached. Saving progress...")
                    self._save_partial_results()
                    print("   🔄 Restarting browser session...")
                    self.driver.quit()
                    time.sleep(8)
                    self.driver = self._setup_driver()
                    self._load_cookies()
                    self.search_mbg()
                    last_post_count = 0
                
            except Exception as e:
                print(f"   ❌ Scroll attempt failed: {e}")
                time.sleep(SCROLL_RECOVERY_DELAY)
        
        # Final summary
        print("\n✅ Smart scrolling completed")
        print(f"   Total scroll attempts: {self.scroll_attempts}")
        print(f"   Total posts extracted: {len(self.posts_data)}")
        print(f"   Session duration: {time.time() - self.start_time:.1f} seconds")

    def _incremental_scroll(self):
        """Scroll bertahap untuk menghindari deteksi bot"""
        # Scroll in small increments
        for i in range(3):
            scroll_height = (i + 1) * (self.driver.execute_script("return document.body.scrollHeight") // 3)
            self.driver.execute_script(f"window.scrollTo(0, {scroll_height});")
            time.sleep(0.5)
        
        # Final scroll to bottom
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    def _extract_new_posts(self):
        """Ekstrak post baru dengan deduplication"""
        try:
            posts = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
            print(f"   Found {len(posts)} posts on page")
            
            new_count = 0
            for post in posts:
                if len(self.posts_data) >= MAX_POSTS:
                    break
                
                post_hash = self._get_post_hash(post)
                if post_hash in self.processed_posts:
                    continue
                
                post_data = self._parse_single_post(post)
                if post_data:
                    self.processed_posts.add(post_hash)
                    self.posts_data.append(post_data)
                    new_count += 1
            
            return new_count
            
        except Exception as e:
            print(f"   ❌ Extraction error: {e}")
            return 0

    def _get_post_hash(self, post):
        """Generate unique hash untuk deduplication"""
        try:
            content_hash = post.get_attribute('outerHTML')[:200]
            return hash(content_hash)
        except:
            return hash(time.time())

    def _parse_single_post(self, post):
        """Parse single post dengan error handling production"""
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
            
            # Skip if content too short or empty
            if not content or len(content) < 15:
                return None
            
            # Timestamp
            timestamp = datetime.now().isoformat()
            try:
                time_element = post.find_element(By.CSS_SELECTOR, "time")
                timestamp = time_element.get_attribute("datetime")
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
            
            return {
                "platform": "twitter",
                "search_keyword": "MBG",
                "username": username,
                "content": content,
                "timestamp": timestamp,
                "likes": likes,
                "retweets": retweets,
                "scraped_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            return None

    def _save_partial_results(self):
        """Simpan hasil sementara untuk session restart"""
        if not self.posts_data:
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"MBG_partial_{len(self.posts_data)}_posts_{timestamp}.{OUTPUT_FORMAT}"
            filepath = os.path.join(OUTPUT_FOLDER, filename)
            
            df = pd.DataFrame(self.posts_data)
            
            if OUTPUT_FORMAT == "csv":
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
            else:
                df.to_json(filepath, orient='records', indent=2, ensure_ascii=False)
            
            print(f"   💾 Saved partial results: {filename}")
            return filepath
            
        except Exception as e:
            print(f"   ❌ Partial save failed: {e}")
            return None

    def save_final_results(self):
        """Simpan hasil akhir dengan metadata lengkap"""
        if not self.posts_data:
            print("❌ No data to save")
            return False
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"MBG_ALL_{len(self.posts_data)}_posts_{timestamp}.{OUTPUT_FORMAT}"
            filepath = os.path.join(OUTPUT_FOLDER, filename)
            
            df = pd.DataFrame(self.posts_data)
            
            # Add metadata columns
            df['scraper_version'] = "2.0"
            df['target_keyword'] = "MBG"
            df['extraction_date'] = datetime.now().isoformat()
            df['session_duration'] = f"{time.time() - self.start_time:.1f} seconds"
            df['scroll_attempts'] = self.scroll_attempts
            
            # Save
            if OUTPUT_FORMAT == "csv":
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
            else:
                df.to_json(filepath, orient='records', indent=2, ensure_ascii=False)
            
            # Save metadata
            metadata = {
                "scraper_info": {
                    "name": "Production MBG Twitter Scraper",
                    "version": "2.0",
                    "target_posts": MAX_POSTS,
                    "actual_posts": len(self.posts_data),
                    "extraction_date": datetime.now().isoformat(),
                    "session_duration": f"{time.time() - self.start_time:.1f} seconds",
                    "scroll_attempts": self.scroll_attempts,
                    "keywords_used": ["MBG"],
                    "output_file": filepath
                },
                "statistics": {
                    "unique_authors": len(df['username'].unique()),
                    "avg_content_length": df['content'].apply(len).mean(),
                    "avg_likes": df['likes'].apply(lambda x: int(x.replace(',', '')) if x.replace(',', '').isdigit() else 0).mean()
                }
            }
            
            metadata_file = os.path.join(OUTPUT_FOLDER, f"MBG_metadata_{timestamp}.json")
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            print("\n✅ Final results saved successfully")
            print(f"   📁 Data file: {filepath}")
            print(f"   📁 Metadata file: {metadata_file}")
            print(f"   📊 Total posts: {len(self.posts_data)}")
            print(f"   👥 Unique authors: {metadata['statistics']['unique_authors']}")
            print(f"   ⏱️ Session duration: {metadata['scraper_info']['session_duration']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Final save failed: {e}")
            return False

    def run(self):
        """Main production execution flow"""
        print("🚀 Starting PRODUCTION Twitter Scraper for 'MBG'")
        print("=" * 60)
        print(f"🎯 Target: {MAX_POSTS} MBG posts (All Time)")
        print(f"⏱️  Max session duration: {MAX_SESSION_DURATION/60:.1f} minutes")
        print(f"🔄 Max scroll attempts: {MAX_SCROLL_ATTEMPTS}")
        print("-" * 60)
        
        self.start_time = time.time()
        
        try:
            # Initialize driver
            self.driver = self._setup_driver()
            
            # Load cookies and login
            if not self._load_cookies():
                print("❌ Login failed. Cannot proceed with scraping.")
                return
            
            # Search for MBG
            if not self.search_mbg():
                print("❌ Search failed. Cannot proceed with scraping.")
                return
            
            # Smart scrolling until target reached
            self._smart_scroll_until_target()
            
            # Save final results
            if self.posts_data:
                self.save_final_results()
            else:
                print("❌ No MBG posts were extracted. Check your cookies and connection.")
                self.driver.save_screenshot("no_posts_extracted.png")
            
        except Exception as e:
            print(f"❌ Critical error in production scraper: {e}")
            if self.driver:
                self.driver.save_screenshot("production_crash.png")
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