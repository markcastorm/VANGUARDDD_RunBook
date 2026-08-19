# scraper.py
# Web scraper for Vanguard ETF Average Duration data — fully RPA-tag driven

import time
import logging
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fallback JS: scan the entire document for the most-frequent "as of DATE"
# ---------------------------------------------------------------------------
_JS_SCAN_DOC_DATE = """
var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
var re = /as of (\\d{1,2}\\/\\d{1,2}\\/\\d{4})/i;
var freq = {};
var node;
while (node = walker.nextNode()) {
    var m = node.textContent.match(re);
    if (m) freq[m[1]] = (freq[m[1]] || 0) + 1;
}
var keys = Object.keys(freq);
if (!keys.length) return null;
keys.sort(function(a, b) { return freq[b] - freq[a]; });
return keys[0];
"""

# ---------------------------------------------------------------------------
# Fallback JS: find symbolAvgDuration via DOM — fund cell, not benchmark
# ---------------------------------------------------------------------------
_JS_SCAN_DURATION = """
var re = /^\\d+\\.?\\d*\\s*years?$/i;
// First try: element with the exact RPA tag
var el = document.querySelector('[data-rpa-tag-id="symbolAvgDuration"]');
if (el) { var t = el.textContent.trim(); if (re.test(t)) return t; }
// Fallback: walk table rows, pick label "average duration", return fund cell (index 1)
var rows = document.querySelectorAll('tr');
for (var i = 0; i < rows.length; i++) {
    var cells = rows[i].querySelectorAll('td');
    if (cells.length < 2) continue;
    if (cells[0].textContent.trim().toLowerCase().indexOf('average duration') < 0) continue;
    var val = cells[1].textContent.trim();
    if (re.test(val)) return val;
}
return null;
"""


class VanguardDDScraper:
    """Scrapes Average Duration data from Vanguard ETF pages.

    Identification strategy: Vanguard embeds stable data-rpa-tag-id attributes
    throughout the page for automation. We use these exclusively — no CSS class
    names that may change between site deployments.
    """

    def __init__(self):
        self.driver = None
        self.logger = logger

    # ------------------------------------------------------------------
    # Driver setup
    # ------------------------------------------------------------------

    def setup_driver(self):
        opts = Options()
        if config.HEADLESS_MODE:
            opts.add_argument('--headless')
            opts.add_argument('--disable-gpu')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1920,1080')
        opts.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.driver = webdriver.Chrome(options=opts)
        self.driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
        self.logger.info("Chrome driver initialized")

    def _build_url(self, ticker):
        return f"https://investor.vanguard.com/etf/profile/overview/{ticker.lower()}"

    # ------------------------------------------------------------------
    # Cookie consent popup
    # ------------------------------------------------------------------

    def dismiss_cookie_popup(self):
        """Click the cookie-accept button if a consent popup is visible. Non-fatal.

        Uses a single instant JS call — no per-selector Selenium waits — so we
        don't waste time when the popup is absent (which is most of the time).
        """
        try:
            clicked = self.driver.execute_script("""
                var candidates = [
                    document.querySelector('#onetrust-accept-btn-handler'),
                    document.querySelector('.onetrust-accept-btn-handler'),
                    document.querySelector('button[title*="Accept"]'),
                    document.querySelector('button[aria-label*="Accept"]')
                ];
                for (var i = 0; i < candidates.length; i++) {
                    var btn = candidates[i];
                    if (btn && btn.offsetParent !== null) {
                        btn.click();
                        return btn.id || btn.textContent.trim().substring(0, 40);
                    }
                }
                // Text-based fallback
                var btns = document.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    var t = btns[i].textContent.trim().toLowerCase();
                    if ((t === 'accept' || t.indexOf('accept all') === 0)
                            && btns[i].offsetParent !== null) {
                        btns[i].click();
                        return btns[i].textContent.trim().substring(0, 40);
                    }
                }
                return null;
            """)
            if clicked:
                self.logger.info(f"Cookie popup dismissed: {clicked!r}")
                time.sleep(0.5)  # brief pause for popup animation
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Navigation — waits for Angular to bootstrap via RPA tag presence
    # ------------------------------------------------------------------

    def navigate_to_page(self, url):
        """Load page and wait for Angular to bootstrap.

        Angular's JS bundle occasionally stalls on a fresh session (cold CDN hit).
        After a timeout we refresh once — the bundle is now cached so bootstrap
        completes in seconds on the second attempt.
        """
        self.logger.info(f"Navigating to {url}")
        for load_attempt in range(2):
            try:
                if load_attempt == 0:
                    self.driver.get(url)
                else:
                    self.logger.info("Angular stalled — refreshing page (bundle now cached)")
                    self.driver.refresh()

                # Dismiss any cookie/privacy popup that may block rendering
                self.dismiss_cookie_popup()

                # Angular has bootstrapped when at least one RPA tag is in the DOM
                WebDriverWait(self.driver, config.ELEMENT_WAIT_TIMEOUT).until(
                    lambda d: d.execute_script(
                        "return document.querySelectorAll('[data-rpa-tag-id]').length > 0"
                    )
                )

                # Fund ticker heading confirms we're on the right page
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, '[data-rpa-tag-id="dashboard-symbol"]')
                    )
                )
                symbol = self.driver.find_element(
                    By.CSS_SELECTOR, '[data-rpa-tag-id="dashboard-symbol"]'
                ).text.strip()
                self.logger.info(f"Page ready — fund: {symbol!r}")
                return True

            except TimeoutException:
                if load_attempt == 0:
                    self.logger.warning(
                        f"Angular did not bootstrap within {config.ELEMENT_WAIT_TIMEOUT}s — will refresh"
                    )
                    continue
                self.logger.error("Page failed to become ready even after refresh")
                return False
            except Exception as e:
                self.logger.error(f"Navigation error: {e}")
                return False

        return False

    # ------------------------------------------------------------------
    # Section scroll — waits for symbolAvgDuration to render
    # ------------------------------------------------------------------

    def scroll_to_portfolio_composition(self):
        """Scroll to the portfolio section; wait for the duration cell to appear."""
        self.logger.info("Scrolling to Portfolio Composition section...")
        try:
            # Locate by id attribute (stable) rather than combined tag+id selector
            section = WebDriverWait(self.driver, config.ELEMENT_WAIT_TIMEOUT).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[id*="portfolio-composition"]')
                )
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});",
                section
            )

            # Wait for the exact element we need — this IS the fund duration cell
            WebDriverWait(self.driver, config.TABLE_WAIT_TIMEOUT).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[data-rpa-tag-id="symbolAvgDuration"]')
                )
            )
            self.logger.info("Portfolio Composition rendered (symbolAvgDuration present)")
            return True

        except TimeoutException:
            self.logger.warning("Timed out waiting for symbolAvgDuration to render")
            return False
        except Exception as e:
            self.logger.error(f"Scroll error: {e}")
            return False

    # ------------------------------------------------------------------
    # Fund name verification — via RPA tag
    # ------------------------------------------------------------------

    def verify_fund_name(self, ticker, expected_name):
        try:
            el = self.driver.find_element(
                By.CSS_SELECTOR, '[data-rpa-tag-id="dashboard-symbol"]'
            )
            found = el.text.strip()
            if ticker.upper() in found:
                self.logger.info(f"Verified fund: {found!r}")
                return True
            self.logger.warning(f"Ticker {ticker.upper()!r} not in heading {found!r}")
            return False
        except Exception:
            self.logger.warning("Could not verify fund name — continuing anyway")
            return True

    # ------------------------------------------------------------------
    # Date extraction — RPA-tag driven with JS fallback
    # ------------------------------------------------------------------

    def extract_as_of_date(self):
        """Return the portfolio characteristics 'as of' date as MM/DD/YYYY, or None."""
        self.logger.info("Extracting portfolio characteristics date...")

        # Portfolio characteristics date — confirmed present on all three ETFs
        for rpa_id in ('holdingDetailDate', 'summaryDate', 'cumulativeDate'):
            date = self._date_via_rpa(rpa_id)
            if date:
                return date

        # Final fallback: full-document JS scan for most-frequent "as of DATE"
        return self._date_via_js(_JS_SCAN_DOC_DATE, 'JS full-document scan')

    def _date_via_rpa(self, rpa_id):
        try:
            el = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, f'[data-rpa-tag-id="{rpa_id}"]')
                )
            )
            date = self._parse_date(el.text.strip())
            if date:
                self.logger.info(f"Date via RPA [{rpa_id}]: {date}")
                return date
        except TimeoutException:
            self.logger.debug(f"RPA [{rpa_id}] not found within timeout")
        except Exception as e:
            self.logger.debug(f"RPA [{rpa_id}] error: {e}")
        return None

    def _date_via_js(self, script, label):
        try:
            result = self.driver.execute_script(script)
            if result:
                date = self._parse_date(result)
                if date:
                    self.logger.info(f"Date via {label}: {date}")
                    return date
        except Exception as e:
            self.logger.debug(f"JS date strategy {label!r} error: {e}")
        return None

    def _parse_date(self, text):
        """Extract MM/DD/YYYY from text, stripping any 'as of' prefix."""
        if not text:
            return None
        clean = re.sub(r'(?i)^as\s+of\s+', '', text.strip()).strip()
        m = re.search(r'\d{1,2}/\d{1,2}/\d{4}', clean)
        return m.group(0) if m else None

    # ------------------------------------------------------------------
    # Duration extraction — symbolAvgDuration RPA tag (fund column only)
    # ------------------------------------------------------------------

    def extract_average_duration(self, ticker):
        """Return the fund's Average Duration as a string (e.g. '6.0 years'), or None.

        Uses symbolAvgDuration — Vanguard's RPA tag for the fund (VCIT/VCSH/VCLT)
        column value. Never touches benchmarkAvgDuration.
        """
        self.logger.info(f"Extracting Average Duration for {ticker}...")

        # Strategy 1: RPA tag symbolAvgDuration — fund column, not benchmark
        try:
            el = WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[data-rpa-tag-id="symbolAvgDuration"]')
                )
            )
            val = el.text.strip()
            if val and val not in ('—', '-', ''):
                self.logger.info(f"Duration via RPA [symbolAvgDuration]: {val}")
                return val
        except TimeoutException:
            self.logger.debug("RPA [symbolAvgDuration] timed out")
        except Exception as e:
            self.logger.debug(f"RPA [symbolAvgDuration] error: {e}")

        # Strategy 2: JS DOM scan — finds symbolAvgDuration or walks rows by label text
        try:
            result = self.driver.execute_script(_JS_SCAN_DURATION)
            if result:
                self.logger.info(f"Duration via JS scan: {result}")
                return result
        except Exception as e:
            self.logger.debug(f"JS duration scan error: {e}")

        # Strategy 3: XPath text match — finds any row whose first cell contains
        # "average duration" (case-insensitive), returns the second cell (fund value).
        # Survives CSS/RPA changes as long as the label text and table structure exist.
        val = self._duration_via_xpath_text()
        if val:
            return val

        self.logger.error(f"All duration strategies failed for {ticker}")
        return None

    def _duration_via_xpath_text(self):
        """XPath text-based fallback: find 'Average duration' row, return fund cell."""
        _duration_re = re.compile(r'^\d+\.?\d*\s*years?$', re.I)
        try:
            # Case-insensitive XPath via translate() — no CSS classes involved
            xpath = (
                "//tr[td[contains("
                "translate(normalize-space(.), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                "'abcdefghijklmnopqrstuvwxyz'), "
                "'average duration')]]"
            )
            rows = self.driver.find_elements(By.XPATH, xpath)
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, 'td')
                if len(cells) < 2:
                    continue
                # cells[0] = label, cells[1] = fund value, cells[2] = benchmark
                val = cells[1].text.strip()
                if val and _duration_re.match(val):
                    self.logger.info(f"Duration via XPath text scan: {val}")
                    return val
        except Exception as e:
            self.logger.debug(f"XPath duration scan error: {e}")
        return None

    # ------------------------------------------------------------------
    # Per-product scrape with retry
    # ------------------------------------------------------------------

    def scrape_product(self, ticker, expected_name):
        url = self._build_url(ticker)
        self.logger.info(f"\n{'='*70}\nScraping {ticker}: {url}\n{'='*70}")

        for attempt in range(1, config.MAX_RETRIES + 1):
            if attempt > 1:
                self.logger.info(f"Retry {attempt}/{config.MAX_RETRIES} for {ticker}")
                time.sleep(config.RETRY_DELAY)

            try:
                if not self.navigate_to_page(url):
                    continue

                self.verify_fund_name(ticker, expected_name)

                if not self.scroll_to_portfolio_composition():
                    self.logger.warning("Scroll issue — attempting extraction with current DOM")

                date_str = self.extract_as_of_date()
                if not date_str:
                    self.logger.error(f"Date extraction failed (attempt {attempt})")
                    continue

                duration_str = self.extract_average_duration(ticker)
                if not duration_str:
                    self.logger.error(f"Duration extraction failed (attempt {attempt})")
                    continue

                self.logger.info(
                    f"SUCCESS {ticker}: date={date_str}, duration={duration_str}"
                )
                return {'product': ticker, 'date_str': date_str, 'duration_str': duration_str}

            except Exception as e:
                self.logger.error(f"Error scraping {ticker} (attempt {attempt}): {e}")

        self.logger.error(f"All {config.MAX_RETRIES} attempts failed for {ticker}")
        return None

    # ------------------------------------------------------------------
    # Scrape all products
    # ------------------------------------------------------------------

    def scrape_all_products(self):
        try:
            self.setup_driver()
            results = {}

            for col_info in config.OUTPUT_COLUMNS:
                ticker = col_info['url_key']
                expected_name = col_info['fund_name']
                data = self.scrape_product(ticker, expected_name)

                if data:
                    results[ticker] = data
                elif config.REQUIRE_ALL_PRODUCTS:
                    self.logger.error(f"Required product {ticker} failed — aborting")
                    return None

            if not results:
                self.logger.error("No products scraped successfully")
                return None

            self.logger.info(f"\nScraped {len(results)}/3 products successfully")
            return results

        except Exception as e:
            self.logger.error(f"Fatal scraping error: {e}")
            return None

        finally:
            if self.driver:
                self.driver.quit()
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
            print(f"  Date:     {data.get('date_str')}")
            print(f"  Duration: {data.get('duration_str')}")
    else:
        print("\n[FAILED] Could not extract data")


if __name__ == '__main__':
    main()
