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