import sys
import os
import json
from datetime import datetime

# Get current file directory and project root
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)

# Import settings
try:
    from config.settings import KEYWORDS
except ImportError:
    # Fallback loading
    config_dir = os.path.join(project_root, "config")
    keywords_file = os.path.join(config_dir, "keywords.json")
    
    if os.path.exists(keywords_file):
        try:
            with open(keywords_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                KEYWORDS = data.get("mbg_keywords", ["mbg prabowo"])
        except:
            KEYWORDS = ["mbg prabowo"]
    else:
        KEYWORDS = ["mbg prabowo"]
# Import the scraper
from scrapers.twitter_scraper import ProductionTwitterScraper

def main():
    """Main execution function"""
    print("🚀 Twitter Scraper Production Mode")
    print("=" * 50)
    print(f"Keywords: {', '.join(KEYWORDS)}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Initialize and run scraper
    scraper = ProductionTwitterScraper()
    scraper.run()
    
    print("\n✅ Session completed")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()