import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from scrapers.facebook_scraper import FacebookScraper
from config.settings import KEYWORDS, OUTPUT_FOLDER, OUTPUT_FORMAT

def main():
    scraper = FacebookScraper(
        keywords=KEYWORDS,
        output_folder=OUTPUT_FOLDER,
        output_format=OUTPUT_FORMAT
    )
    scraper.run()

if __name__ == "__main__":
    main()