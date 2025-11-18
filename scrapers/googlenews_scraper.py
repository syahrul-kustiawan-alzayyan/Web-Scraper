from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import time
import pandas as pd
import os
import random
from datetime import datetime, timedelta
import json
import urllib.parse
import re
import sys
from config.settings import (
    SELENIUM_DRIVER_PATH,
    BROWSER_HEADLESS,
    SCROLL_DELAY,
    PAGE_LOAD_DELAY,
    MAX_POSTS,
    OUTPUT_FOLDER,
    OUTPUT_FORMAT,
    KEYWORDS
)

class GoogleNewsScraper:
    def __init__(self):
        self.driver = None
        self.posts_data = []
        self.processed_posts = set()
        self.start_time = None
        self.scroll_attempts = 0
        self.target_keyword = KEYWORDS[0] if KEYWORDS else "program mbg"
        self.article_base_url = "https://news.google.com"
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
        ]

    def _setup_driver(self):
        """Setup Chrome driver dengan konfigurasi anti-detection maksimal"""
        print("🔧 Setting up Google News Chrome driver with anti-detection...")
        options = Options()
        
        # Essential production options
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-renderer-backgrounding")
        
        # Critical anti-detection settings
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-automation")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-plugins-discovery")
        options.add_argument("--mute-audio")
        options.add_argument("--disable-logging")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-bundled-ppapi-flash")
        options.add_argument("--disable-backgrounding-occluded-windows")
        
        # Realistic user agent rotation
        selected_user_agent = random.choice(self.user_agents)
        options.add_argument(f"user-agent={selected_user_agent}")
        print(f"   🧑‍💻 Using user agent: {selected_user_agent}")
        
        # Exclude automation switches
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Performance optimization
        options.add_argument("--enable-features=NetworkService,NetworkServiceInProcess")
        options.add_argument("--disable-features=VizDisplayCompositor")
        
        if BROWSER_HEADLESS:
            options.add_argument("--headless=new")
            # Headless-specific optimizations
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--disable-dev-shm-usage")
        
        service = Service(SELENIUM_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
        
        # Advanced anti-detection JavaScript
        driver.execute_script("""
        // Remove WebDriver properties
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Remove Chrome properties
        window.navigator.chrome = {
            runtime: {},
            app: {}
        };
        
        // Remove plugins and languages
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        // Remove permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
        );
        """)
        
        print("✅ Google News Chrome driver initialized with anti-detection")
        return driver

    def search_keyword(self):
        """Search Google News dengan strategi multi-layer"""
        print(f"\n🔍 Searching Google News for: '{self.target_keyword}'")
        
        # Multiple search strategies with fallback URLs
        search_strategies = [
            {
                "name": "indonesian_region",
                "url": f"https://news.google.com/search?q={urllib.parse.quote(self.target_keyword)}&hl=id&gl=ID&ceid=ID:id",
                "description": "Indonesian region (primary)"
            },
            {
                "name": "english_global",
                "url": f"https://news.google.com/search?q={urllib.parse.quote(self.target_keyword)}&hl=en&gl=US&ceid=US:en",
                "description": "English global (fallback 1)"
            },
            {
                "name": "topic_news",
                "url": f"https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pWVXlnQVAB?hl=en&gl=US&ceid=US%3Aen&q={urllib.parse.quote(self.target_keyword)}",
                "description": "Topic-based news (fallback 2)"
            },
            {
                "name": "basic_search",
                "url": f"https://news.google.com/search?q={urllib.parse.quote(self.target_keyword)}",
                "description": "Basic search (fallback 3)"
            }
        ]
        
        for strategy in search_strategies:
            print(f"\n🎯 Trying search strategy: {strategy['name']}")
            print(f"   📌 {strategy['description']}")
            print(f"   💻 URL: {strategy['url']}")
            
            try:
                # Open URL with retry mechanism
                self._get_with_retry(strategy['url'], max_retries=3)
                
                # Take initial screenshot
                self.driver.save_screenshot(f"googlenews_{strategy['name']}_initial.png")
                
                # Handle cookie consent with multiple strategies
                self._handle_cookie_consent()
                
                # Verify page loaded with multiple validation methods
                if self._verify_page_loaded(strategy['name']):
                    print(f"✅ Google News search page loaded successfully with strategy: {strategy['name']}")
                    return True
                
                print(f"❌ Search results not found with strategy: {strategy['name']}")
                self.driver.save_screenshot(f"googlenews_{strategy['name']}_failed.png")
                time.sleep(3)
                
            except Exception as e:
                print(f"❌ Strategy {strategy['name']} failed: {str(e)}")
                self.driver.save_screenshot(f"googlenews_{strategy['name']}_error.png")
                time.sleep(5)
                continue
        
        print("\n❌ ALL SEARCH STRATEGIES FAILED")
        self.driver.save_screenshot("googlenews_all_strategies_failed.png")
        return False

    def _get_with_retry(self, url, max_retries=3):
        """Get URL dengan mekanisme retry yang robust"""
        for attempt in range(max_retries):
            try:
                print(f"   🌐 Attempt {attempt+1}/{max_retries} to load URL...")
                self.driver.get(url)
                
                # Wait for page to start loading
                time.sleep(PAGE_LOAD_DELAY)
                
                # Check if page loaded successfully
                if self._is_page_responsive():
                    print("   ✅ Page loaded successfully")
                    return
                
                print(f"   ⚠️ Page not responsive on attempt {attempt+1}")
                time.sleep(3)
                
            except WebDriverException as e:
                print(f"   ❌ WebDriver error on attempt {attempt+1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
            
            except Exception as e:
                print(f"   ❌ Unexpected error on attempt {attempt+1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
        
        raise Exception("Failed to load URL after maximum retries")

    def _is_page_responsive(self):
        """Check if page is responsive and not blocked"""
        try:
            # Check page title
            title = self.driver.title
            if "blocked" in title.lower() or "captcha" in title.lower():
                return False
            
            # Check page content
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            if "unusual traffic" in body_text or "captcha" in body_text or "blocked" in body_text:
                return False
            
            return True
        except:
            return False

    def _handle_cookie_consent(self):
        """Handle cookie consent dengan strategi multi-layer"""
        print("   🍪 Handling cookie consent...")
        
        try:
            # Setiap strategi cookie consent
            consent_strategies = [
                {
                    "name": "xpath_accept",
                    "selectors": [
                        "//button[contains(text(),'Accept') or contains(text(),'accept') or contains(text(),'Setuju') or contains(text(),'I agree')]",
                        "//button[@aria-label='Accept']",
                        "//button[contains(@aria-label, 'accept') or contains(@aria-label, 'setuju')]"
                    ]
                },
                {
                    "name": "css_accept",
                    "selectors": [
                        "[aria-label*='accept']",
                        "[aria-label*='setuju']",
                        "button[data-action='accept']",
                        "button[aria-label*='Accept']"
                    ]
                },
                {
                    "name": "indonesian_buttons",
                    "selectors": [
                        "//button[contains(text(),'Setuju')]",
                        "//button[contains(text(),'Ya')]",
                        "//button[contains(text(),'Ok')]"
                    ]
                }
            ]
            
            for strategy in consent_strategies:
                print(f"   🧪 Trying cookie strategy: {strategy['name']}")
                
                for selector in strategy['selectors']:
                    try:
                        if selector.startswith("//"):
                            # XPath selector
                            element = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                        else:
                            # CSS selector
                            element = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                        
                        print(f"   ✅ Found cookie button with selector: {selector}")
                        element.click()
                        time.sleep(2)
                        
                        # Verify button disappeared
                        try:
                            WebDriverWait(self.driver, 2).until_not(
                                EC.visibility_of(element)
                            )
                            print("   ✅ Cookie consent accepted successfully")
                            return True
                        except:
                            print("   ⚠️ Cookie button still visible after click")
                            continue
                            
                    except Exception as e:
                        continue
            
            print("   ℹ️ No cookie consent banner found or already accepted")
            return False
            
        except Exception as e:
            print(f"   ❌ Error handling cookie consent: {str(e)}")
            return False

    def _verify_page_loaded(self, strategy_name):
        """Verifikasi halaman Google News termuat dengan benar"""
        print("   ✅ Verifying page loaded...")
        
        try:
            # Strategy 1: Check for main content container
            main_content_selectors = [
                "c-wiz[role='main']",  # Modern Google News
                "div[data-nbg]",       # Alternative structure
                "main",                # Main content
                "div[jscontroller]"    # Controller-based
            ]
            
            for selector in main_content_selectors:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    print(f"   ✅ Main content container found: {selector}")
                    break
                except:
                    continue
            else:
                print("   ❌ No main content container found")
                return False
            
            # Strategy 2: Check for articles
            article_selectors = [
                "c-wiz > div > div > article",  # Modern structure
                "div[data-nbg] article",        # Alternative structure
                "article[jscontroller]",        # Controller-based
                "div[role='article']",          # ARIA role
                "div.S7RlWe"                    # Legacy Google News
            ]
            
            article_found = False
            for selector in article_selectors:
                try:
                    articles = WebDriverWait(self.driver, 8).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                    if articles and len(articles) > 0:
                        print(f"   ✅ Found {len(articles)} articles using selector: {selector}")
                        article_found = True
                        break
                except:
                    continue
            
            if not article_found:
                print("   ❌ No articles found on page")
                # Take screenshot for debugging
                self.driver.save_screenshot(f"no_articles_{strategy_name}.png")
                return False
            
            # Strategy 3: Check page title contains search keyword
            title = self.driver.title.lower()
            keyword_lower = self.target_keyword.lower()
            if keyword_lower not in title and "google news" not in title:
                print(f"   ⚠️ Unexpected page title: '{title}'")
                # Continue anyway as this might be normal
            
            print("   🎯 Page verification passed successfully")
            return True
            
        except Exception as e:
            print(f"   ❌ Page verification failed: {str(e)}")
            self.driver.save_screenshot(f"page_verification_failed_{strategy_name}.png")
            return False

    def _smart_scroll_until_target(self):
        """Scrolling cerdas untuk Google News"""
        print(f"\n🔄 Starting smart scrolling for Google News '{self.target_keyword}'...")
        print("=" * 60)
        
        self.start_time = time.time()
        last_article_count = 0
        no_new_content_count = 0
        articles_found = 0
        
        while (self.scroll_attempts < 40 and  # Increased scroll attempts
               len(self.posts_data) < MAX_POSTS and
               time.time() - self.start_time < 900):  # 15 minutes max
            
            self.scroll_attempts += 1
            elapsed_time = time.time() - self.start_time
            print(f"\n📈 Scroll Attempt {self.scroll_attempts}/40 | Elapsed: {elapsed_time:.1f}s")
            print(f"   Current articles: {len(self.posts_data)}/{MAX_POSTS}")
            
            try:
                # Step 1: Scroll down in small increments
                print("   ⬇️ Scrolling page incrementally...")
                for i in range(3):
                    scroll_height = (i + 1) * (self.driver.execute_script("return document.body.scrollHeight") // 3)
                    self.driver.execute_script(f"window.scrollTo(0, {scroll_height});")
                    time.sleep(1)
                
                # Final scroll to bottom
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(SCROLL_DELAY * 1.5)
                
                # Step 2: Extract articles
                new_articles = self._extract_articles()
                articles_found += new_articles
                print(f"   📊 This scroll: {new_articles} new articles | Total: {len(self.posts_data)}")
                
                # Step 3: Check if we have enough articles or reached bottom
                try:
                    current_articles = self.driver.find_elements(By.CSS_SELECTOR, "c-wiz > div > div > article")
                    current_count = len(current_articles)
                    print(f"   📌 Current articles on page: {current_count}")
                    
                    if current_count == last_article_count:
                        no_new_content_count += 1
                        print(f"   ⚠️ No new articles ({no_new_content_count}/5)")
                        
                        if no_new_content_count >= 5:
                            print("   🛑 Stopping scroll - no new articles after 5 attempts")
                            break
                    else:
                        no_new_content_count = 0
                        last_article_count = current_count
                    
                except Exception as e:
                    print(f"   ⚠️ Article count check failed: {str(e)}")
                
                # Step 4: Random delay to avoid detection
                delay = random.uniform(2, 4)
                print(f"   ⏳ Waiting {delay:.1f} seconds before next scroll...")
                time.sleep(delay)
                
            except Exception as e:
                print(f"   ❌ Scroll attempt failed: {str(e)}")
                # Take screenshot for debugging
                self.driver.save_screenshot(f"scroll_failed_{self.scroll_attempts}.png")
                time.sleep(5)
        
        print("\n✅ Google News scrolling completed")
        print(f"   Total scroll attempts: {self.scroll_attempts}")
        print(f"   Total articles extracted: {len(self.posts_data)}")
        print(f"   Session duration: {time.time() - self.start_time:.1f} seconds")
        print(f"   Success rate: {len(self.posts_data)/articles_found*100:.1f}%" if articles_found > 0 else "N/A")

    def _get_valid_articles(self):
        """Get valid article elements with robust selectors"""
        print("   🔍 Finding Google News articles...")
        
        try:
            # Multiple strategies to find articles
            article_selectors = [
                {
                    "name": "modern_structure",
                    "selector": "c-wiz > div > div > article"
                },
                {
                    "name": "alternative_structure",
                    "selector": "div[data-nbg] article"
                },
                {
                    "name": "controller_based",
                    "selector": "article[jscontroller]"
                },
                {
                    "name": "aria_role",
                    "selector": "div[role='article']"
                },
                {
                    "name": "legacy_structure",
                    "selector": "div.S7RlWe"
                }
            ]
            
            for strategy in article_selectors:
                try:
                    print(f"   🎯 Trying article strategy: {strategy['name']}")
                    articles = self.driver.find_elements(By.CSS_SELECTOR, strategy['selector'])
                    
                    if articles and len(articles) > 0:
                        print(f"   ✅ Found {len(articles)} articles using strategy: {strategy['name']}")
                        return articles
                    
                    print(f"   ⚠️ No articles found with strategy: {strategy['name']}")
                    
                except Exception as e:
                    print(f"   ❌ Strategy {strategy['name']} failed: {str(e)}")
                    continue
            
            print("   ❌ No articles found with any strategy")
            self.driver.save_screenshot("no_articles_found_final.png")
            return []
            
        except Exception as e:
            print(f"   ❌ Critical error finding articles: {str(e)}")
            self.driver.save_screenshot("critical_article_finding_error.png")
            return []

    def _extract_articles(self):
        """Ekstrak artikel dari Google News"""
        new_count = 0
        
        try:
            # Get valid articles
            articles = self._get_valid_articles()
            if not articles:
                return 0
            
            print(f"   📌 Found {len(articles)} articles to process")
            
            # Process each article
            for i, article in enumerate(articles):
                if len(self.posts_data) >= MAX_POSTS:
                    print(f"   ✅ Reached maximum articles limit: {MAX_POSTS}")
                    break
                
                print(f"   🔄 Processing article {i+1}/{len(articles)}")
                
                try:
                    # Get article data
                    article_data = self._parse_article_preview(article)
                    
                    # Validate and add to results
                    if article_data and self._is_valid_article(article_data):
                        article_id = hash(article_data['title'] + article_data['source'] + article_data['article_url'])
                        
                        if article_id not in self.processed_posts:
                            self.processed_posts.add(article_id)
                            self.posts_data.append(article_data)
                            new_count += 1
                            print(f"   ✅ [{len(self.posts_data)}/{MAX_POSTS}] Added: {article_data['source']} - {article_data['title'][:50]}...")
                    
                except Exception as e:
                    print(f"   ❌ Error processing article {i+1}: {str(e)}")
                    continue
            
            return new_count
            
        except Exception as e:
            print(f"   ❌ Critical error in article extraction: {str(e)}")
            self.driver.save_screenshot("critical_extraction_error.png")
            return 0

    def _parse_article_preview(self, article):
        """Parse Google News article preview data dengan fallback strategies"""
        try:
            # Get title (multiple strategies)
            title = ""
            title_strategies = [
                "h3",                          # Standard title
                "div[role='heading']",         # ARIA heading
                "a > div > div > div:first-child",  # Complex structure
                "div[jsname]"                  # JavaScript name
            ]
            
            for selector in title_strategies:
                try:
                    title_element = article.find_element(By.CSS_SELECTOR, selector)
                    title = title_element.text.strip()
                    if title and len(title) > 10:
                        break
                except:
                    continue
            
            if not title or len(title) < 10:
                return None
            
            # Get source and timestamp (multiple strategies)
            source = "unknown"
            timestamp = datetime.now().isoformat()
            
            # Strategy 1: Source and time in same element
            try:
                source_time_element = article.find_element(By.CSS_SELECTOR, "div.SVJrMe, div.UdSxnd, div.QQabt")
                source_time_text = source_time_element.text.strip()
                
                if source_time_text:
                    parts = source_time_text.split(" · ")
                    if len(parts) >= 2:
                        source = parts[0].strip()
                        time_text = parts[1].strip()
                        timestamp = self._parse_relative_time(time_text)
                    elif len(parts) == 1:
                        source = parts[0].strip()
            except:
                pass
            
            # Strategy 2: Separate elements
            if source == "unknown":
                try:
                    source_element = article.find_element(By.CSS_SELECTOR, "div[role='link'], div[aria-label], a")
                    source_text = source_element.text.strip()
                    if source_text and len(source_text) > 2:
                        source = source_text
                except:
                    pass
            
            # Get content/description (multiple strategies)
            content = ""
            content_strategies = [
                "div.Ut6n4e",           # Modern description
                "div.FNFuQ",            # Alternative description
                "div.HN7Xlf",           # Legacy description
                "div[aria-label]",      # ARIA label
                "span",                 # Fallback span
                "div[jsname]"           # JavaScript name
            ]
            
            for selector in content_strategies:
                try:
                    content_element = article.find_element(By.CSS_SELECTOR, selector)
                    content = content_element.text.strip()
                    if content and len(content) > 20:
                        break
                except:
                    continue
            
            # Get article URL (multiple strategies)
            article_url = ""
            url_strategies = [
                "a",                            # Direct link
                "div[role='link'] a",           # Link in role container
                "article a",                    # Article link
                "div[jscontroller] > div > a"   # Complex structure
            ]
            
            for selector in url_strategies:
                try:
                    link_element = article.find_element(By.CSS_SELECTOR, selector)
                    url = link_element.get_attribute("href")
                    if url:
                        if url.startswith("./"):
                            article_url = self.article_base_url + url[1:]
                        elif url.startswith("/"):
                            article_url = self.article_base_url + url
                        else:
                            article_url = url
                        break
                except:
                    continue
            
            # Get image URL (multiple strategies)
            image_url = ""
            image_strategies = [
                "img",                          # Direct image
                "div[role='img'] img",          # Image in role container
                "figure img",                   # Figure image
                "div[jsname] img"               # JavaScript name
            ]
            
            for selector in image_strategies:
                try:
                    img_element = article.find_element(By.CSS_SELECTOR, selector)
                    src = img_element.get_attribute("src")
                    if src and ("gstatic.com" in src or "google.com" in src):
                        image_url = src
                        break
                except:
                    continue
            
            return {
                "platform": "google_news",
                "search_keyword": self.target_keyword,
                "title": title,
                "content": content,
                "source": source,
                "timestamp": timestamp,
                "article_url": article_url,
                "image_url": image_url,
                "scraped_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"   🚨 Article parsing error: {str(e)}")
            return None

    def _is_valid_article(self, article_data):
        """Validate if article data is valid and relevant"""
        if not article_data:
            return False
        
        # Check title quality
        if len(article_data['title']) < 15:
            return False
        
        # Check relevance to keyword
        keyword_lower = self.target_keyword.lower()
        title_lower = article_data['title'].lower()
        content_lower = article_data['content'].lower()
        
        # List of relevant terms for "program mbg"
        relevant_terms = [
            "mbg", "makan bergizi", "program", "gratis", "sekolah", "siswa", 
            "anak", "prabowo", "kementerian", "pendidikan", "kesehatan"
        ]
        
        # Check if article contains relevant terms
        relevance_score = 0
        for term in relevant_terms:
            if term in title_lower or term in content_lower:
                relevance_score += 1
        
        # Must have at least 2 relevant terms OR contain the exact keyword
        is_relevant = (
            relevance_score >= 2 or
            keyword_lower in title_lower or
            keyword_lower in content_lower
        )
        
        return is_relevant

    def _parse_relative_time(self, time_text):
        """Parse relative time text to datetime dengan support Indonesia"""
        current_time = datetime.now()
        
        try:
            time_text = time_text.lower().strip()
            
            # Indonesian time formats
            if any(term in time_text for term in ["jam", "jam yang lalu"]):
                hours_match = re.search(r'(\d+)', time_text)
                if hours_match:
                    hours = int(hours_match.group(1))
                    return (current_time - timedelta(hours=hours)).isoformat()
            
            elif any(term in time_text for term in ["hari", "hari yang lalu"]):
                days_match = re.search(r'(\d+)', time_text)
                if days_match:
                    days = int(days_match.group(1))
                    return (current_time - timedelta(days=days)).isoformat()
            
            elif any(term in time_text for term in ["minggu", "minggu yang lalu"]):
                weeks_match = re.search(r'(\d+)', time_text)
                if weeks_match:
                    weeks = int(weeks_match.group(1))
                    return (current_time - timedelta(weeks=weeks)).isoformat()
            
            elif any(term in time_text for term in ["bulan", "bulan yang lalu"]):
                months_match = re.search(r'(\d+)', time_text)
                if months_match:
                    months = int(months_match.group(1))
                    return (current_time - timedelta(days=months*30)).isoformat()
            
            # Try to parse as absolute date
            try:
                # Common Indonesian date formats
                if re.search(r'\d{1,2} (jan|feb|mar|apr|mei|jun|jul|agu|sep|okt|nov|des) \d{4}', time_text, re.IGNORECASE):
                    return current_time.isoformat()
            except:
                pass
                
        except Exception as e:
            print(f"   ⚠️ Time parsing error: {str(e)}")
        
        # Return current time as fallback
        return current_time.isoformat()

    def _save_results(self):
        """Simpan hasil Google News scraping"""
        if not self.posts_data:
            print("❌ No Google News articles to save")
            return False
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_keyword = self.target_keyword.replace(" ", "_").replace("/", "_").lower()
            filename = f"googlenews_{safe_keyword}_{len(self.posts_data)}_articles_{timestamp}.{OUTPUT_FORMAT}"
            filepath = os.path.join(OUTPUT_FOLDER, filename)
            
            df = pd.DataFrame(self.posts_data)
            
            # Add metadata
            df['scraper_version'] = "2.0"
            df['extraction_date'] = datetime.now().isoformat()
            df['scroll_attempts'] = self.scroll_attempts
            df['search_strategy'] = "multi-layer"
            df['processing_time'] = f"{time.time() - self.start_time:.1f} seconds"
            
            # Save
            if OUTPUT_FORMAT == "csv":
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
            else:
                df.to_json(filepath, orient='records', indent=2, ensure_ascii=False)
            
            print("\n✅ Google News results saved successfully")
            print(f"   📁 Data file: {filepath}")
            print(f"   📊 Total articles: {len(self.posts_data)}")
            
            # Print sample data
            print("\n📋 Sample of extracted Google News articles:")
            sample_df = df[['source', 'title', 'content']].head(3)
            for idx, row in sample_df.iterrows():
                print(f"   {idx+1}. {row['source']}: {row['title'][:80]}...")
                print(f"      Content: {row['content'][:100]}...")
            
            # Save metadata
            metadata = {
                "scraper_info": {
                    "name": "Google News Scraper",
                    "version": "2.0",
                    "target_keyword": self.target_keyword,
                    "articles_extracted": len(self.posts_data),
                    "extraction_date": datetime.now().isoformat(),
                    "processing_time": f"{time.time() - self.start_time:.1f} seconds",
                    "scroll_attempts": self.scroll_attempts,
                    "output_file": filepath
                },
                "statistics": {
                    "unique_sources": len(df['source'].unique()),
                    "avg_title_length": df['title'].apply(len).mean(),
                    "avg_content_length": df['content'].apply(len).mean(),
                    "articles_with_urls": len(df[df['article_url'].str.contains('http')])
                }
            }
            
            metadata_file = os.path.join(OUTPUT_FOLDER, f"googlenews_metadata_{timestamp}.json")
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            print(f"   💾 Metadata saved to: {metadata_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ Google News save failed: {str(e)}")
            self.driver.save_screenshot("save_failed.png")
            return False

    def run(self):
        """Main execution flow dengan recovery mechanism"""
        print("🚀 Starting Google News Scraper for 'program mbg'")
        print("=" * 60)
        print(f"🎯 Target: {MAX_POSTS} articles containing '{self.target_keyword}'")
        print(f"🛡️  Anti-detection: ENABLED")
        print(f"🔄 Recovery mechanism: ENABLED")
        print("-" * 60)
        
        self.start_time = time.time()
        
        try:
            # Setup driver
            self.driver = self._setup_driver()
            
            # Search for keyword with multiple strategies
            if not self.search_keyword():
                print("❌ All Google News search strategies failed. Cannot proceed with scraping.")
                return
            
            # Scroll and extract articles
            self._smart_scroll_until_target()
            
            # Save results
            if self.posts_data:
                self._save_results()
            else:
                print(f"❌ No Google News articles containing '{self.target_keyword}' were found after {self.scroll_attempts} attempts.")
                print("💡 TIPS FOR SUCCESS:")
                print("   - Try different keywords like 'makan bergizi' or 'prabowo makan'")
                print("   - Run the scraper during off-peak hours (early morning)")
                print("   - Use a different IP address if possible")
                print("   - Reduce target articles to 100 for testing")
                self.driver.save_screenshot("no_articles_final.png")
            
        except Exception as e:
            print(f"❌ Critical error in Google News scraper: {str(e)}")
            import traceback
            traceback.print_exc()
            if self.driver:
                self.driver.save_screenshot("critical_error.png")
        finally:
            try:
                if self.driver:
                    print("\n\n" + "=" * 60)
                    print("   📊 FINAL SCRAPER STATISTICS")
                    print(f"   Total articles extracted: {len(self.posts_data)}")
                    print(f"   Session duration: {time.time() - self.start_time:.1f} seconds")
                    print(f"   Success rate: {len(self.posts_data)/MAX_POSTS*100:.1f}% if target reached")
                    print("=" * 60)
                    
                    print("\n🔌 Closing Google News browser...")
                    self.driver.quit()
                    print("✅ Google News browser closed successfully")
            except Exception as e:
                print(f"❌ Error closing browser: {str(e)}")

if __name__ == "__main__":
    scraper = GoogleNewsScraper()
    scraper.run()