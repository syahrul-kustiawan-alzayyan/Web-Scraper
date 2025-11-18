import sys
import os

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scrapers.instagram_scraper import InstagramScraper

def main():
    print("🚀 Starting Instagram Scraper for 'program mbg'")
    print("=" * 70)
    print("This will scrape up to 1000 posts containing 'program mbg' from Instagram.")
    print("The process may take 20-40 minutes depending on network speed.")
    print("DO NOT close the browser window during scraping.")
    print("-" * 70)
    
    # Confirm start
    confirm = input("Do you want to start the Instagram scraper? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Scraper aborted by user")
        return
    
    scraper = InstagramScraper()
    scraper.run()
    
    print("\n✅ INSTAGRAM SCRAPER COMPLETED")
    print("=" * 40)

if __name__ == "__main__":
    main()