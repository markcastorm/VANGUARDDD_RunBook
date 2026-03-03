# scraper.py
# Web scraper for Vanguard ETF Average Duration data

import time
import logging
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import config

# Setup logging
logger = logging.getLogger(__name__)


class VanguardDDScraper:
    """Scrapes Average Duration data from Vanguard ETF pages"""

    def __init__(self):
        self.driver = None
        self.logger = logger

    def setup_driver(self):
        """Initialize Chrome driver"""

        chrome_options = Options()

        if config.HEADLESS_MODE:
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(config.WAIT_TIMEOUT)

        self.logger.info("Chrome driver initialized")

    def navigate_to_page(self, url):
        """Navigate to the ETF page"""

        self.logger.info(f"Navigating to {url}")

        try:
            self.driver.get(url)
            time.sleep(config.PAGE_LOAD_DELAY)
            self.logger.info("Page loaded successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error loading page: {e}")
            return False

    def scroll_to_portfolio_composition(self):
        """Scroll down to Portfolio Composition section"""

        self.logger.info("Scrolling to Portfolio Composition section...")

        try:
            # Find the Portfolio Composition section
            section = self.driver.find_element(By.CSS_SELECTOR, config.SELECTORS['portfolio_section'])

            # Scroll element into view
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                section
            )
            time.sleep(config.SCROLL_DELAY)
            self.logger.info("Scrolled to Portfolio Composition section")
            return True

        except NoSuchElementException:
            self.logger.error("Portfolio Composition section not found")
            return False
        except Exception as e:
            self.logger.error(f"Error scrolling to section: {e}")
            return False

    def extract_as_of_date(self):
        """
        Extract the "as of" date from the characteristics section.

        Returns:
            str: Date string (e.g., "12/31/2025") or None if not found
        """

        self.logger.info("Extracting 'as of' date...")

        try:
            # Find the date element
            date_element = self.driver.find_element(By.CSS_SELECTOR, config.SELECTORS['date_text'])
            date_text = date_element.text.strip()

            self.logger.debug(f"Raw date text: {date_text}")

            # Remove "as of " prefix if present
            if date_text.lower().startswith('as of '):
                date_text = date_text[6:].strip()

            self.logger.info(f"Found 'as of' date: {date_text}")
            return date_text

        except NoSuchElementException:
            self.logger.error("Could not find 'as of' date element")
            return None
        except Exception as e:
            self.logger.error(f"Error extracting 'as of' date: {e}")
            return None

    def extract_average_duration(self, product_key):
        """
        Extract the Average Duration value from the characteristics table.

        Args:
            product_key: Product identifier (VCIT, VCSH, VCLT)

        Returns:
            str: Duration string (e.g., "6.0 years") or None if not found
        """

        self.logger.info(f"Extracting Average Duration for {product_key}...")

        try:
            # Method 1: Try direct RPA tag access (most reliable)
            try:
                duration_element = self.driver.find_element(
                    By.CSS_SELECTOR,
                    config.SELECTORS['symbol_avg_duration']
                )
                duration_str = duration_element.text.strip()

                if duration_str and duration_str != '—':
                    self.logger.info(f"Found Average Duration (RPA tag): {duration_str}")
                    return duration_str

            except NoSuchElementException:
                self.logger.debug("RPA tag method failed, trying table search...")

            # Method 2: Search through table rows
            table = self.driver.find_element(By.CSS_SELECTOR, config.SELECTORS['fixed_income_table'])
            rows = table.find_elements(By.CSS_SELECTOR, config.SELECTORS['table_rows'])

            for row in rows:
                try:
                    label_cell = row.find_element(By.CSS_SELECTOR, config.SELECTORS['row_header'])
                    label_text = label_cell.text.strip()

                    # Check if this is the Average Duration row
                    if config.SELECTORS['average_duration_label'] in label_text:
                        # Get the data cell (second td in the row)
                        data_cells = row.find_elements(By.TAG_NAME, 'td')
                        if len(data_cells) >= 2:
                            duration_str = data_cells[1].text.strip()

                            if duration_str and duration_str != '—':
                                self.logger.info(f"Found Average Duration (table): {duration_str}")
                                return duration_str

                except NoSuchElementException:
                    continue

            self.logger.error(f"Could not find Average Duration for {product_key}")
            return None

        except NoSuchElementException:
            self.logger.error(f"Table not found for {product_key}")
            return None
        except Exception as e:
            self.logger.error(f"Error extracting Average Duration: {e}")
            return None

    def verify_fund_name(self, expected_product):
        """
        Verify we're on the correct fund page by checking the fund name.

        Args:
            expected_product: Expected product key (VCIT, VCSH, VCLT)

        Returns:
            bool: True if fund name matches, False otherwise
        """

        try:
            fund_name_element = self.driver.find_element(By.CSS_SELECTOR, config.SELECTORS['fund_name_heading'])
            fund_name = fund_name_element.text.strip()

            # Get expected fund name from config
            expected_name = None
            for col_info in config.OUTPUT_COLUMNS:
                if col_info['url_key'] == expected_product:
                    expected_name = col_info['fund_name']
                    break

            if expected_name and expected_name in fund_name:
                self.logger.info(f"Verified fund name: {fund_name}")
                return True
            else:
                self.logger.warning(f"Fund name mismatch. Found: {fund_name}, Expected: {expected_name}")
                return False

        except NoSuchElementException:
            self.logger.warning("Could not verify fund name")
            return True  # Continue anyway

    def scrape_product(self, product_key, url):
        """
        Scrape data for a single product.

        Args:
            product_key: Product identifier (VCIT, VCSH, VCLT)
            url: URL to scrape

        Returns:
            dict with scraped data or None
        """

        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Scraping {product_key}: {url}")
        self.logger.info(f"{'='*70}")

        try:
            # Navigate to page
            if not self.navigate_to_page(url):
                self.logger.error(f"Failed to load page for {product_key}")
                return None

            # Verify fund name
            self.verify_fund_name(product_key)

            # Scroll to Portfolio Composition section
            if not self.scroll_to_portfolio_composition():
                self.logger.warning(f"Could not scroll to Portfolio Composition for {product_key}")
                # Continue anyway - section might be visible

            # Extract "as of" date
            date_str = self.extract_as_of_date()

            if not date_str:
                self.logger.error(f"Failed to extract 'as of' date for {product_key}")
                return None

            # Extract Average Duration
            duration_str = self.extract_average_duration(product_key)

            if not duration_str:
                self.logger.error(f"Failed to extract Average Duration for {product_key}")
                return None

            data = {
                'product': product_key,
                'date_str': date_str,
                'duration_str': duration_str,
            }

            self.logger.info(f"Successfully scraped {product_key}")
            return data

        except Exception as e:
            self.logger.error(f"Error scraping {product_key}: {e}")
            return None

    def scrape_all_products(self):
        """
        Main method to scrape all ETF products.
        Returns dict with data for all products.
        """

        try:
            self.setup_driver()

            results = {}

            # Scrape each product in order
            for col_info in config.OUTPUT_COLUMNS:
                product_key = col_info['url_key']
                url = config.URLS[product_key]

                data = self.scrape_product(product_key, url)

                if data:
                    results[product_key] = data
                elif config.REQUIRE_ALL_PRODUCTS:
                    self.logger.error(f"Required product {product_key} failed - aborting")
                    return None

            if len(results) == 0:
                self.logger.error("No products were successfully scraped")
                return None

            self.logger.info(f"\nSuccessfully scraped {len(results)} products")
            return results

        except Exception as e:
            self.logger.error(f"Error during scraping: {e}")
            return None

        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("Browser closed")


def main():
    """Test the scraper"""
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
