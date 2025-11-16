from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from datetime import datetime
import re
import time
import os
import json

def clean_text(text: str) -> str:
    """Clean and normalize text content"""
    if not text:
        return ""
    
    # Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    
    # Remove special characters except basic punctuation
    text = re.sub(r'[^\w\s,.!?\'"-]', '', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def parse_twitter_post(post_element, driver) -> dict:
    """Parse Twitter post dengan penanganan konten kosong dan error yang benar"""
    try:
        # Cek apakah post element valid
        if not post_element or not post_element.is_displayed():
            print("   ℹ️ Skipping invisible or invalid post element")
            return None
        
        # Strategy 1: Cari dengan selector yang lebih stabil
        try:
            # Username
            username = ""
            try:
                username_element = post_element.find_element(By.CSS_SELECTOR, "[data-testid='User-Name'] a span")
                username = username_element.text
            except Exception as e:
                try:
                    username_element = post_element.find_element(By.CSS_SELECTOR, "[data-testid='UserName'] span")
                    username = username_element.text
                except Exception as e2:
                    try:
                        username_element = post_element.find_element(By.CSS_SELECTOR, "a[href*='status'] span")
                        username = username_element.text
                    except Exception as e3:
                        username = "unknown_user"
                        print(f"   ⚠️ Username extraction fallback: {str(e3)}")
            
            # Content
            content = ""
            try:
                content_element = post_element.find_element(By.CSS_SELECTOR, "[data-testid='tweetText']")
                content = content_element.text
            except Exception as e:
                try:
                    content_element = post_element.find_element(By.CSS_SELECTOR, "div[lang]")
                    content = content_element.text
                except Exception as e2:
                    try:
                        content_elements = post_element.find_elements(By.CSS_SELECTOR, "span")
                        content = " ".join([el.text for el in content_elements if el.text.strip() != ""])
                    except Exception as e3:
                        content = ""
                        print(f"   ⚠️ Content extraction fallback: {str(e3)}")
            
            # Jika konten kosong, lewati
            if not content or not content.strip():
                print("   ⚠️ Skipping post with empty content")
                return None
            
            # Timestamp
            timestamp = datetime.now().isoformat()
            try:
                time_element = post_element.find_element(By.CSS_SELECTOR, "time")
                timestamp = time_element.get_attribute("datetime")
            except Exception as e:
                try:
                    time_text = post_element.find_element(By.CSS_SELECTOR, "[aria-label]").get_attribute("aria-label")
                    if "ago" in time_text.lower():
                        timestamp = f"relative: {time_text}"
                except Exception as e2:
                    # Gunakan timestamp sekarang sebagai fallback
                    timestamp = datetime.now().isoformat()
                    print(f"   ⚠️ Timestamp fallback to current time: {str(e2)}")
            
            # Engagement metrics
            likes = "0"
            retweets = "0"
            
            try:
                like_elements = post_element.find_elements(By.CSS_SELECTOR, "[data-testid*='like']")
                for el in like_elements:
                    try:
                        text = el.text.strip()
                        if text and text.replace(',', '').isdigit():
                            likes = text
                            break
                    except Exception as e:
                        continue
            except Exception as e:
                print(f"   ⚠️ Likes extraction error: {str(e)}")
            
            try:
                retweet_elements = post_element.find_elements(By.CSS_SELECTOR, "[data-testid*='retweet']")
                for el in retweet_elements:
                    try:
                        text = el.text.strip()
                        if text and text.replace(',', '').isdigit():
                            retweets = text
                            break
                    except Exception as e:
                        continue
            except Exception as e:
                print(f"   ⚠️ Retweets extraction error: {str(e)}")
            
            # Clean the data
            content = clean_text(content)
            username = clean_text(username)
            
            # Filter konten terlalu pendek
            if len(content) < 15:
                print(f"   ⚠️ Skipping short content ({len(content)} chars): {content[:30]}...")
                return None
            
            result = {
                "platform": "twitter",
                "username": username,
                "content": content,
                "timestamp": timestamp,
                "likes": likes,
                "retweets": retweets,
                "scraped_at": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            print(f"   🚨 Strategy 1 parsing failed: {str(e)}")
            # Simpan screenshot untuk debugging
            try:
                post_element.screenshot(f"parsing_error_{int(time.time())}.png")
                print("   📸 Saved error screenshot")
            except:
                pass
        
        return None
        
    except Exception as e:
        print(f"   🔥 CRITICAL parsing error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def parse_instagram_post(driver) -> dict:
    """Parse Instagram post details from current active post"""
    try:
        # Get username
        username = driver.find_element(By.CSS_SELECTOR, "div.x9f619.x1n2onr6.x1ja2u2z > a").text
        
        # Get post content
        content = driver.find_element(By.CSS_SELECTOR, "div._a9zs > span").text
        content = clean_text(content)
        
        # Get timestamp
        timestamp = driver.find_element(By.CSS_SELECTOR, "time").get_attribute("datetime")
        
        # Get engagement metrics
        likes = driver.find_element(By.CSS_SELECTOR, "div._aamw > span").text or "0"
        
        return {
            "platform": "instagram",
            "username": clean_text(username),
            "content": content,
            "timestamp": timestamp,
            "likes": likes,
            "scraped_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Instagram post parsing error: {e}")
        return None

def parse_facebook_post(post_element: WebElement) -> dict:
    """Parse Facebook post element into structured data"""
    try:
        # Get username
        username = post_element.find_element(By.CSS_SELECTOR, "span.a8c37x1j.ni8dbmo4.stjg6sef.l9j0dhe7").text
        
        # Get post content
        content = post_element.find_element(By.CSS_SELECTOR, "div.x1iorvi4.x1pi30zi.x1swvt13.x1d0u1a7").text
        content = clean_text(content)
        
        # Get timestamp
        timestamp = post_element.find_element(By.CSS_SELECTOR, "span.x193iq5w.xeuugli.x13faqbe.x1vvkbs.x10flsy6.x1cr53u4.x1d0u1a7.x1g7wq7j").get_attribute("title")
        
        # Get engagement metrics
        likes = post_element.find_element(By.CSS_SELECTOR, "span.x193iq5w.xeuugli.x13faqbe.x1vvkbs.x10flsy6.x1cr53u4.x1d0u1a7.x1g7wq7j").text or "0"
        
        return {
            "platform": "facebook",
            "username": clean_text(username),
            "content": content,
            "timestamp": timestamp,
            "likes": likes,
            "scraped_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Facebook post parsing error: {e}")
        return None

def parse_googlenews_article(article_element) -> dict:
    """Parse Google News article element into structured data"""
    try:
        # Get title
        title = article_element.find_element(By.CSS_SELECTOR, "h3").text
        
        # Get source and timestamp
        source_info = article_element.find_element(By.CSS_SELECTOR, "div.QmrVtf").text
        source, timestamp = source_info.split(" - ") if " - " in source_info else (source_info, "")
        
        # Get content snippet
        content = article_element.find_element(By.CSS_SELECTOR, "div.e2Kufb").text
        
        return {
            "platform": "google_news",
            "title": clean_text(title),
            "source": clean_text(source),
            "timestamp": timestamp,
            "content": clean_text(content),
            "scraped_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Google News article parsing error: {e}")
        return None