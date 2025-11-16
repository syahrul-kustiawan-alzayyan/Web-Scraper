from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import random

def scroll_page(driver, scroll_delay=3, max_scrolls=10):
    """Scroll page dengan delay yang lebih realistis untuk per-keyword search"""
    print("\n🔄 Starting page scrolling...")
    print("-" * 40)
    
    scroll_count = 0
    last_post_count = 0
    no_new_content_count = 0
    
    while scroll_count < max_scrolls:
        scroll_count += 1
        print(f"\n⬇️ Scroll attempt {scroll_count}/{max_scrolls}")
        
        try:
            # Strategy 1: Scroll dengan JavaScript
            print("   Executing JavaScript scroll...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_delay * 0.7)
            
            # Strategy 2: Scroll dengan keyboard (simulasi human)
            print("   Simulating human-like scrolling...")
            actions = ActionChains(driver)
            for _ in range(random.randint(2, 4)):
                actions.send_keys(Keys.PAGE_DOWN).perform()
                time.sleep(random.uniform(0.3, 0.8))
            
            # Strategy 3: Scroll ke elemen terakhir
            try:
                posts = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
                if posts:
                    last_tweet = posts[-1]
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'end'});", last_tweet)
                    time.sleep(scroll_delay * 0.5)
                    print(f"   Found {len(posts)} posts for targeted scroll")
            except Exception as e:
                print(f"   ℹ️ No posts found for targeted scroll: {str(e)}")
            
            # Wait for content to load
            wait_time = random.uniform(scroll_delay * 0.8, scroll_delay * 1.2)
            print(f"   Waiting for content to load... ({wait_time:.1f}s)")
            time.sleep(wait_time)
            
            # Check if new content loaded
            try:
                current_posts = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
                current_count = len(current_posts)
                
                print(f"   Posts found: {current_count}")
                
                if current_count > last_post_count:
                    print(f"   ✅ New content loaded (+{current_count - last_post_count} posts)")
                    last_post_count = current_count
                    no_new_content_count = 0
                else:
                    no_new_content_count += 1
                    print(f"   ⚠️ No new content loaded (attempt {no_new_content_count}/3)")
                    
                    if no_new_content_count >= 3:
                        print("   🛑 Stopping scroll - no new content after 3 attempts")
                        break
            except Exception as e:
                print(f"   ❌ Error checking content: {str(e)}")
            
        except Exception as e:
            print(f"   ❌ Scroll attempt failed: {str(e)}")
            time.sleep(2)
    
    print("\n✅ Scrolling completed")
    print(f"   Total scroll attempts: {scroll_count}")
    print(f"   Stopped because: {'max scrolls reached' if scroll_count >= max_scrolls else 'no new content'}")
    
    return scroll_count