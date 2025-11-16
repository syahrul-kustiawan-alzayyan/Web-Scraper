import sys
import os

# Tambahkan root project ke path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Import dan jalankan scraper
from scrapers.twitter_scraper import TwitterScraper

def main():
    print("🎯 Running Twitter Scraper for 'MBG' ONLY")
    print("-" * 40)
    
    scraper = TwitterScraper()
    scraper.run()
    
    print("\n✅ Scraping completed")

if __name__ == "__main__":
    main()