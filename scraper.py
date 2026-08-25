# scraper.py
# Web scraper for Vanguard ETF Average Duration data

import time
import logging
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import config

logger = logging.getLogger(__name__)


class VanguardDDScraper:
    """Scrapes Average Duration data from Vanguard ETF pages"""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
        self.logger = logger

    def setup_driver(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=config.HEADLESS_MODE,
            args=['--window-size=1920,1080']
        )
        context = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            )
        )
        self._page = context.new_page()
        Stealth().apply_stealth_sync(self._page)
        self.logger.info("Playwright browser initialized")

    def _quit(self):
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

    def navigate_to_page(self, url):
        try:
            self.logger.info(f"Loading {url}")
            self._page.goto(url, wait_until='domcontentloaded', timeout=config.PAGE_LOAD_TIMEOUT * 1000)
            time.sleep(10)

            hash_url = url + '#portfolio-composition'
            self.logger.info(f"Navigating to {hash_url}")
            self._page.goto(hash_url, wait_until='domcontentloaded', timeout=config.PAGE_LOAD_TIMEOUT * 1000)
            time.sleep(6)

            self.logger.info("Page loaded successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error loading page: {e}")
            return False

    def scroll_to_portfolio_composition(self):
        section = self._page.query_selector('section#portfolio-composition')
        if section:
            section.scroll_into_view_if_needed()
            time.sleep(2)
            self.logger.info("Scrolled to Portfolio Composition section")
            return True
        self.logger.error("Portfolio Composition section not found")
        return False

    def extract_as_of_date(self):
        self.logger.info("Extracting 'as of' date...")
        for selector in ('p.date.rps-paragraph-two', 'p.date'):
            el = self._page.query_selector(selector)
            if el:
                date_text = el.inner_text().strip()
                if date_text.lower().startswith('as of '):
                    date_text = date_text[6:].strip()
                self.logger.info(f"Found 'as of' date: {date_text}")
                return date_text
        self.logger.error("Could not find 'as of' date element")
        return None

    def extract_average_duration(self, product_key):
        self.logger.info(f"Extracting Average Duration for {product_key}...")

        # Method 1: RPA tag
        el = self._page.query_selector('td[data-rpa-tag-id="symbolAvgDuration"]')
        if el:
            val = el.inner_text().strip()
            if val and val != '—':
                self.logger.info(f"Found Average Duration (RPA tag): {val}")
                return val

        # Method 2: table rows
        rows = self._page.query_selector_all('tr.fixed-income')
        self.logger.debug(f"tr.fixed-income rows: {len(rows)}")
        for row in rows:
            header = row.query_selector('td.row-header')
            if header and 'Average duration' in header.inner_text():
                cells = row.query_selector_all('td')
                if len(cells) >= 2:
                    val = cells[1].inner_text().strip()
                    if val and val != '—':
                        self.logger.info(f"Found Average Duration (table): {val}")
                        return val

        self.logger.error(f"Could not find Average Duration for {product_key}")
        return None

    def scrape_product(self, product_key, url):
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Scraping {product_key}: {url}")
        self.logger.info(f"{'='*70}")

        if not self.navigate_to_page(url):
            return None

        self.scroll_to_portfolio_composition()

        date_str = self.extract_as_of_date()
        if not date_str:
            self.logger.error(f"Failed to extract 'as of' date for {product_key}")
            return None

        duration_str = self.extract_average_duration(product_key)
        if not duration_str:
            self.logger.error(f"Failed to extract Average Duration for {product_key}")
            return None

        self.logger.info(f"Successfully scraped {product_key}")
        return {'product': product_key, 'date_str': date_str, 'duration_str': duration_str}

    def scrape_all_products(self):
        try:
            self.setup_driver()
            results = {}

            for col_info in config.OUTPUT_COLUMNS:
                product_key = col_info['url_key']
                url = config.URLS[product_key]

                data = self.scrape_product(product_key, url)
                if data:
                    results[product_key] = data
                elif config.REQUIRE_ALL_PRODUCTS:
                    self.logger.error(f"Required product {product_key} failed — aborting")
                    return None

            if not results:
                self.logger.error("No products were successfully scraped")
                return None

            self.logger.info(f"Successfully scraped {len(results)} products")
            return results

        except Exception as e:
            self.logger.error(f"Error during scraping: {e}")
            return None

        finally:
            self._quit()
            self.logger.info("Browser closed")


def main():
    from logger_setup import setup_logging
    setup_logging()

    scraper = VanguardDDScraper()
    results = scraper.scrape_all_products()

    if results:
        print("\n[SUCCESS] Data extracted")
        for product, data in results.items():
            print(f"\n{product}:")
            print(f"  Date: {data.get('date_str')}")
            print(f"  Duration: {data.get('duration_str')}")
    else:
        print("\n[FAILED] Could not extract data")


if __name__ == '__main__':
    main()
