import sys
import os

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scrapers.twitter_scraper import ProductionTwitterScraper

def main():
    print("🚀 Starting PRODUCTION Twitter Scraper for 1000 MBG Posts")
    print("=" * 70)
    print("This will scrape up to 1000 posts containing 'MBG' from Twitter.")
    print("The process may take 15-30 minutes depending on network speed.")
    print("DO NOT close the browser window during scraping.")
    print("-" * 70)
    
    # Confirm start
    confirm = input("Do you want to start the production scraper? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Scraper aborted by user")
        return
    
    scraper = ProductionTwitterScraper()
    scraper.run()
    
    print("\n✅ PRODUCTION SCRAPER COMPLETED")
    print("=" * 40)

if __name__ == "__main__":
    main()