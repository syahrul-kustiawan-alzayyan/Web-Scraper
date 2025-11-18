import sys
import os

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scrapers.googlenews_scraper import GoogleNewsScraper

def main():
    print("🚀 Starting PRODUCTION Google News Scraper")
    print("=" * 70)
    print("✅ NO LOGIN REQUIRED - Scraping public Google News content")
    print("🎯 Target: 1000 news articles containing 'program mbg'")
    print("🛡️  Advanced anti-detection and recovery mechanisms enabled")
    print("⏱️  Estimated time: 10-25 minutes (depending on network and rate limiting)")
    print("-" * 70)
    
    print("🔧 System Information:")
    print(f"   Python version: {sys.version.split()[0]}")
    print(f"   Project root: {PROJECT_ROOT}")
    print(f"   Output folder: {os.path.abspath('output')}")
    print("-" * 70)
    
    scraper = GoogleNewsScraper()
    scraper.run()
    
    print("\n✅ GOOGLE NEWS SCRAPER COMPLETED")
    print("=" * 40)

if __name__ == "__main__":
    main()