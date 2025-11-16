# Note: Google News scraper is not required per your "ketiga web" request,
# but included since it appears in your directory structure
from scrapers.googlenews_scraper import GoogleNewsScraper
from config.settings import KEYWORDS, OUTPUT_FOLDER, OUTPUT_FORMAT

def main():
    scraper = GoogleNewsScraper(
        keywords=KEYWORDS,
        output_folder=OUTPUT_FOLDER,
        output_format=OUTPUT_FORMAT
    )
    scraper.run()

if __name__ == "__main__":
    main()