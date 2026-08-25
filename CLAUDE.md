# CLAUDE.md — VANGUARDDD RunBook
## Complete Technical Reference for AI-Assisted Development

> **Purpose:** This file gives any new Claude session full context about this codebase — architecture, data flow, every important function, gotchas, and current state — so you never have to read the source files to get oriented.

---

## 1. Project Summary

**VANGUARDDD** is a daily data pipeline that scrapes bond duration data from Vanguard's website for three ETFs and maintains a cumulative historical master Excel file.

| Ticker | Fund | Metric |
|--------|------|--------|
| VCIT | Vanguard Intermediate-Term Corporate Bond ETF | Average Duration |
| VCSH | Vanguard Short-Term Corporate Bond ETF | Average Duration |
| VCLT | Vanguard Long-Term Corporate Bond ETF | Average Duration |

**Run command (production):**
```
python orchestrator.py
```

**Output:** DATA xlsx + META xlsx + ZIP, written to `output/` and mirrored to `output/latest/`. Master historical file at `Master/Master_DATA.xlsx`.

---

## 2. Repository Layout

```
VANGUARDDD_RunBook/
│
├── orchestrator.py          # ENTRY POINT — chains scraper → parser → file_generator
├── scraper.py               # Playwright browser automation + data extraction
├── parser.py                # Forward/backfill decision logic + master data management
├── file_generator.py        # Excel (DATA, META) + ZIP generation
├── config.py                # ALL configuration — URLs, selectors, column mappings, paths
├── logger_setup.py          # One-time logging bootstrap called by orchestrator
│
├── Master/
│   ├── Master_DATA.xlsx     # THE cumulative historical file (never delete)
│   └── tracking_state.json  # Stopgap state: last as_of_date + last duration values
│
├── output/
│   ├── VANGUARDDD_DATA_<timestamp>.xlsx
│   ├── VANGUARDDD_META_<timestamp>.xlsx
│   ├── VANGUARDDD_<timestamp>.zip
│   └── latest/              # Always mirrors the most recent run's files
│
├── logs/
│   └── vanguarddd_<timestamp>.log
│
└── project_information/     # Reference materials, sample HTML, original requirements
```

---

## 3. Technology Stack

| Layer | Library | Why |
|-------|---------|-----|
| Browser automation | `playwright` (sync API) | Handles JavaScript-heavy Angular SPA |
| Bot detection evasion | `playwright_stealth` (`Stealth` class) | Prevents Vanguard's "automated browser" detection |
| Data | `pandas`, `openpyxl` | Excel read/write |
| Runtime | Python 3.11 | Windows, tested on Windows 11 |

**Critical: Do NOT use Selenium or undetected-chromedriver.** Both were abandoned:
- Standard Selenium → "Chrome Profile error occurred" dialog + bot detection banner
- undetected-chromedriver → crashed on Chrome 151 (version_main not supported)
- Playwright + Stealth → works cleanly, immune to Chrome auto-updates (uses bundled Chromium)

---

## 4. File-by-File Reference

---

### 4.1 `config.py` — All Configuration

**Never hardcode anything in the other files.** Everything lives here.

#### URLs
```python
VANGUARD_BASE_URL = 'https://investor.vanguard.com/investment-products/etfs/profile'

URLS = {
    'VCIT': f'{VANGUARD_BASE_URL}/vcit',
    'VCSH': f'{VANGUARD_BASE_URL}/vcsh',
    'VCLT': f'{VANGUARD_BASE_URL}/vclt',
}
```
> **Gotcha:** The old URL format (`/etf/profile/overview/{ticker}`) is dead — those pages don't load the portfolio section. The current format is `/investment-products/etfs/profile/{ticker}`.

#### CSS Selectors
```python
SELECTORS = {
    'portfolio_section':    'section#portfolio-composition',
    'date_text':            'p.date.rps-paragraph-two',     # Primary date selector
    'symbol_avg_duration':  'td[data-rpa-tag-id="symbolAvgDuration"]',  # Primary duration
    'fixed_income_table':   'fixed-income-characteristic table.width',   # Fallback table
    'table_rows':           'tr.fixed-income',              # Fallback row scan
    'row_header':           'td.row-header',
    'average_duration_label': 'Average duration',
    'fund_name_heading':    'h1.ticker span.fund-name',
}
```
> **Selector strategy:** Primary is the RPA tag (`data-rpa-tag-id="symbolAvgDuration"`). If that fails, scan `tr.fixed-income` rows looking for a `td.row-header` with text "Average duration". In practice, the RPA tag always hits — fallback has never been needed in production.

#### Output Column Definitions (ORDER IS FIXED)
```python
OUTPUT_COLUMNS = [
    {
        'code':         'VANGUARDDD.INTERMEDIATETERMCORPORATEBONDETF.AVGDURATION.B',
        'code_mnemonic':'VANGUARDDD.INTERMEDIATETERMCORPORATEBONDETF.AVGDURATION',
        'description':  'Vanguard Intermediate-Term Corporate Bond ETF, Portfolio composition, Average duration',
        'product':      'VCIT',
        'url_key':      'VCIT',   # key into URLS dict
        'unit':         'years',
        'metric':       'Average duration',
        'fund_name':    'Vanguard Intermediate-Term Corporate Bond ETF'
    },
    # VCSH (index 1), VCLT (index 2) follow same structure
]
```
> **Column order is absolute.** Master_DATA.xlsx columns 1/2/3 correspond to OUTPUT_COLUMNS[0/1/2]. Do not reorder.

#### Key Tunable Settings
```python
HEADLESS_MODE = False          # False = visible browser (good for debugging)
DEBUG_MODE    = True           # Enables DEBUG log level

PAGE_LOAD_TIMEOUT = 60         # Playwright goto timeout (seconds)
# Internally multiplied by 1000 for playwright's millisecond API

REQUIRE_ALL_PRODUCTS = True    # Abort if any ticker fails — do not set False in prod
REBUILD_MASTER       = False   # If True, wipes and rebuilds master from scratch (DANGEROUS)

MIN_DURATION_VALUE = 0.1       # Validation floor (years)
MAX_DURATION_VALUE = 30.0      # Validation ceiling (years)

DATE_FORMAT_OUTPUT = '%Y-%m-%d'  # All dates stored as YYYY-MM-DD in master + tracking
INPUT_DATE_FORMATS = [           # Website date parsing — tries these in order
    '%m/%d/%Y',   # 07/31/2026 ← what Vanguard currently returns
    '%m-%d-%Y',
    '%Y-%m-%d',
    '%B %d, %Y',
    '%b %d, %Y',
]
```

#### File Paths (absolute, hardcoded to this machine)
```python
MASTER_DATA_FILE = r'D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\Master\Master_DATA.xlsx'
TRACKING_FILE    = r'D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\Master\tracking_state.json'
```

---

### 4.2 `scraper.py` — Browser Automation

**Class:** `VanguardDDScraper`

#### Instance variables
| Variable | Set in | Purpose |
|----------|--------|---------|
| `self._playwright` | `setup_driver()` | Playwright context manager handle |
| `self._browser` | `setup_driver()` | Chromium browser instance |
| `self._page` | `setup_driver()` | Active page (shared across all tickers) |

#### `setup_driver()` — Browser initialisation
```python
def setup_driver(self):
```
- Calls `sync_playwright().start()` — must be matched by `self._playwright.stop()` in `_quit()`
- Launches Chromium with `headless=config.HEADLESS_MODE`
- Sets viewport 1920×1080, UA string pinned to Chrome 131 (cosmetic, doesn't affect function)
- Applies `Stealth().apply_stealth_sync(page)` — patches JS properties that fingerprint automated browsers
- **One browser, one page for all three tickers** — no re-launch between tickers

#### `_quit()` — Teardown
```python
def _quit(self):
```
- Called in `scrape_all_products()` finally block
- Closes browser then stops playwright — order matters

#### `navigate_to_page(url)` — Two-step navigation (critical)
```python
def navigate_to_page(self, url):
```
- **Step 1:** `page.goto(url)` — loads the Angular SPA base, waits `domcontentloaded`, then `time.sleep(10)` for JS to bootstrap
- **Step 2:** `page.goto(url + '#portfolio-composition')` — navigates to the hash anchor which triggers lazy-loading of the portfolio section, then `time.sleep(6)`

> **Why two steps?** Navigating directly to `#portfolio-composition` on a cold page does not reliably trigger the lazy-load. The base URL must load first to bootstrap Angular, then the hash navigation fires the route change that renders the section.

#### `scroll_to_portfolio_composition()` — Scroll trigger
```python
def scroll_to_portfolio_composition(self):
```
- Finds `section#portfolio-composition` and calls `scroll_into_view_if_needed()`
- `time.sleep(2)` after scroll — gives Angular time to render the characteristics table

#### `extract_as_of_date()` — Date extraction
```python
def extract_as_of_date(self):
```
- Tries `p.date.rps-paragraph-two` first, then `p.date` as fallback
- Strips "as of " prefix before returning → returns bare date string e.g. `"07/31/2026"`
- Parsing to datetime object happens downstream in `parser.py`

#### `extract_average_duration(product_key)` — Duration extraction
```python
def extract_average_duration(self, product_key):
```
- **Method 1 (primary):** `td[data-rpa-tag-id="symbolAvgDuration"]` — returns e.g. `"2.7 years"`
- **Method 2 (fallback):** Scans `tr.fixed-income` rows, matches `td.row-header` text containing `"Average duration"`, returns `cells[1].inner_text()`
- Returns None if both methods fail

#### `scrape_product(product_key, url)` — Single ticker
```python
def scrape_product(self, product_key, url) -> dict | None:
```
Returns:
```python
{
    'product':      'VCSH',
    'date_str':     '07/31/2026',   # raw, unparsed
    'duration_str': '2.7 years'     # raw, unparsed
}
```

#### `scrape_all_products()` — Main entry point
```python
def scrape_all_products(self) -> dict | None:
```
- Calls `setup_driver()` once
- Iterates `config.OUTPUT_COLUMNS` in order (VCIT → VCSH → VCLT)
- On any failure: if `config.REQUIRE_ALL_PRODUCTS` is True, returns None immediately
- Returns dict keyed by product_key: `{'VCIT': {...}, 'VCSH': {...}, 'VCLT': {...}}`
- Always calls `_quit()` in finally block

---

### 4.3 `parser.py` — Data Logic

**Class:** `VanguardDDParser`

This is the brain of the pipeline — it compares scraped data against last known state and decides what to write to master.

#### `parse_date(date_str)` — Date parsing
```python
def parse_date(self, date_str) -> datetime | None:
```
- Tries all formats in `config.INPUT_DATE_FORMATS` in order
- Returns `datetime` object or None

#### `parse_duration_value(duration_str)` — Duration parsing
```python
def parse_duration_value(self, duration_str) -> float | None:
```
- Strips "years"/"year" suffix, converts to float
- Validates against `MIN_DURATION_VALUE` / `MAX_DURATION_VALUE`
- Returns float or None

#### `parse_scraped_data(scraped_results)` — Build parsed dict
```python
def parse_scraped_data(self, scraped_results) -> dict | None:
```
Returns:
```python
{
    'as_of_date':     datetime(2026, 7, 31),
    'as_of_date_str': '2026-07-31',
    'durations': {
        'VANGUARDDD.INTERMEDIATETERMCORPORATEBONDETF.AVGDURATION.B': 6.0,
        'VANGUARDDD.SHORTTERMCORPORATEBONDETF.AVGDURATION.B':        2.7,
        'VANGUARDDD.LONGTERMCORPORATEBONDETF.AVGDURATION.B':         11.8,
    }
}
```
> "as of" date is taken from the first product — all three always share the same date.

#### `load_tracking_state()` — Read stopgap JSON
```python
def load_tracking_state(self) -> dict | None:
```
- Returns None if `tracking_state.json` doesn't exist (first-ever run)
- Converts `as_of_date` and `last_run_date` strings back to `datetime` objects

#### `save_tracking_state(as_of_date, durations, last_run_date)` — Write stopgap JSON
```python
def save_tracking_state(self, as_of_date, durations, last_run_date):
```
Writes:
```json
{
  "as_of_date": "2026-07-31",
  "durations": {
    "VANGUARDDD.INTERMEDIATETERMCORPORATEBONDETF.AVGDURATION.B": 6.0,
    "VANGUARDDD.SHORTTERMCORPORATEBONDETF.AVGDURATION.B": 2.7,
    "VANGUARDDD.LONGTERMCORPORATEBONDETF.AVGDURATION.B": 11.8
  },
  "last_run_date": "2026-08-25",
  "last_updated": "2026-08-25 09:12:36"
}
```
> `durations` keys are the full `code` strings from `OUTPUT_COLUMNS`, not ticker names.

#### `load_master_data()` / `save_master_data(df)` — Excel I/O
```python
def load_master_data(self) -> pd.DataFrame | None:
def save_master_data(self, df):
```
- Reads/writes `Master_DATA.xlsx` with `header=None` (headers are in rows 0 and 1)
- `save_master_data` normalises column 0: converts any datetime to plain `YYYY-MM-DD` string to prevent timezone-aware Excel artefacts

#### `find_date_row_index(df, target_date)` — Row lookup
```python
def find_date_row_index(self, df, target_date) -> int | None:
```
- Scans df column 0 from row index 2 onward (skipping the 2 header rows)
- Returns 0-based DataFrame index or None if not found

#### `update_master_with_forward_fill(df, today, durations)` — Scenario 1
```python
def update_master_with_forward_fill(self, df, today, durations) -> pd.DataFrame:
```
- Checks if today's row already exists → skips if so (idempotent)
- Appends one new row: `[today_str, vcit_val, vcsh_val, vclt_val]`

#### `update_master_with_backfill(df, as_of_date, durations, today)` — Scenarios 2 & 3
```python
def update_master_with_backfill(self, df, as_of_date, durations, today) -> pd.DataFrame:
```
- Finds `as_of_date` row in master → updates all rows from that index to end with new values
- If `today > last_date_in_master`: appends new business-day rows (weekends skipped) up to today
- Backfill limit: `MAX_BACKFILL_DAYS = 365`

#### `parse_and_merge(scraped_results)` — Main decision method
```python
def parse_and_merge(self, scraped_results) -> pd.DataFrame | None:
```

**Decision tree:**
```
tracking exists?
├── YES
│   ├── date unchanged AND values unchanged → FORWARD-FILL (Scenario 1)
│   ├── date changed                        → BACKFILL    (Scenario 2)
│   └── values changed                      → BACKFILL    (Scenario 3)
└── NO (first run)                          → FORWARD-FILL (just add today's row)
```

After updating master:
1. Calls `save_master_data(df)` — persists to Master_DATA.xlsx
2. Calls `save_tracking_state(...)` — persists to tracking_state.json

---

### 4.4 `file_generator.py` — Output Files

**Class:** `VanguardDDFileGenerator`

#### `create_data_file(master_df, output_dir)` — DATA xlsx
- Writes the full master DataFrame to `VANGUARDDD_DATA_<timestamp>.xlsx`
- `header=False, index=False` — DataFrame rows 0/1 are the headers

#### `create_meta_file(output_dir)` — META xlsx
- Builds a fresh DataFrame from `config.OUTPUT_COLUMNS` + `config.METADATA_DEFAULTS`
- Writes `VANGUARDDD_META_<timestamp>.xlsx` with standard column headers
- Includes `PROVIDER_MEASURE_URL` = the Vanguard URL for each ticker

#### `create_zip_file(data_file, meta_file, output_dir)` — ZIP
- Zips DATA + META into `VANGUARDDD_<timestamp>.zip`

#### `copy_to_latest(files, latest_dir)` — Mirror
- Copies all three files to `output/latest/` (overwrites previous run)

#### `generate_files(master_df)` — Main entry point
- Calls the above four methods in order
- Returns dict: `{'data_file': path, 'meta_file': path, 'zip_file': path}`

---

### 4.5 `orchestrator.py` — Pipeline Coordinator

**Entry point:** `python orchestrator.py`

Execution sequence:
1. `setup_logging()` — initialises file + console logging
2. `VanguardDDScraper().scrape_all_products()` → `scraped_results`
3. `VanguardDDParser().parse_and_merge(scraped_results)` → `updated_master_df`
4. `VanguardDDFileGenerator().generate_files(updated_master_df)` → output files
5. Prints summary to console

**Exit codes:**
- 0 = success
- 1 = any failure (scrape, parse, or file generation)
- 130 = KeyboardInterrupt

---

### 4.6 `logger_setup.py` — Logging Bootstrap

**Function:** `setup_logging()`
- Called once at the start of `orchestrator.py` (and each component's `main()` for standalone testing)
- Creates `logs/` directory if missing
- Sets up root logger with both file handler and console handler
- Log file: `logs/vanguarddd_<RUN_TIMESTAMP>.log`
- Log level driven by `config.LOG_LEVEL` (DEBUG when `DEBUG_MODE=True`)

---

## 5. Master Data File Structure

`Master/Master_DATA.xlsx` — never delete, always keep backed up.

```
Row 0:  [blank]     | VANGUARDDD.INTERMEDIATETERMCORPORATEBONDETF.AVGDURATION.B | VANGUARDDD.SHORTTERMCORPORATEBONDETF.AVGDURATION.B | VANGUARDDD.LONGTERMCORPORATEBONDETF.AVGDURATION.B
Row 1:  [blank]     | Vanguard Intermediate-Term... description                  | Vanguard Short-Term... description                  | Vanguard Long-Term... description
Row 2:  2024-02-29  | 5.8                                                         | 2.5                                                  | 11.4
Row 3:  2024-03-01  | 5.8                                                         | 2.5                                                  | 11.4
...
Row N:  2026-08-25  | 6.0                                                         | 2.7                                                  | 11.8   ← latest (653 rows as of 2026-08-25)
```

- Column 0: date string `YYYY-MM-DD` (no datetime objects — normalised on save)
- Columns 1–3: float values, corresponding to VCIT / VCSH / VCLT in that order
- Business days only — weekends are skipped
- Some older rows may show `6` instead of `6.0` (integer vs float display) — harmless

---

## 6. Tracking State File

`Master/tracking_state.json` — the stopgap / change-detection store.

**Current state as of 2026-08-25:**
```json
{
  "as_of_date": "2026-07-31",
  "durations": {
    "VANGUARDDD.INTERMEDIATETERMCORPORATEBONDETF.AVGDURATION.B": 6.0,
    "VANGUARDDD.SHORTTERMCORPORATEBONDETF.AVGDURATION.B": 2.7,
    "VANGUARDDD.LONGTERMCORPORATEBONDETF.AVGDURATION.B": 11.8
  },
  "last_run_date": "2026-08-25",
  "last_updated": "2026-08-25 09:12:36"
}
```

- `as_of_date` — the "as of" date that Vanguard reported on the last successful run
- `durations` — the values from that run (keyed by full CODE, not ticker)
- `last_run_date` — the calendar date the pipeline last ran (not the as_of date)
- `last_updated` — wall-clock timestamp of last write

---

## 7. Data Flow Diagram

```
Vanguard Website
  └─ /investment-products/etfs/profile/{vcit,vcsh,vclt}#portfolio-composition
       │
       │  Playwright + Stealth (headless=False by default)
       │  Step 1: goto(base_url), sleep 10s
       │  Step 2: goto(hash_url), sleep 6s, scroll, sleep 2s
       ▼
scraper.py  →  scraped_results = {
                  'VCIT': {'date_str': '07/31/2026', 'duration_str': '6.0 years'},
                  'VCSH': {'date_str': '07/31/2026', 'duration_str': '2.7 years'},
                  'VCLT': {'date_str': '07/31/2026', 'duration_str': '11.8 years'},
               }
       │
       ▼
parser.py   →  1. parse_scraped_data() → as_of_date=2026-07-31, durations={code: float}
               2. load_tracking_state() → last known state from JSON
               3. load_master_data()    → full DataFrame (653 rows)
               4. DECISION: forward-fill or backfill
               5. save_master_data()    → Master_DATA.xlsx updated
               6. save_tracking_state() → tracking_state.json updated
       │
       ▼
file_generator.py → VANGUARDDD_DATA_<ts>.xlsx  (copy of master)
                    VANGUARDDD_META_<ts>.xlsx  (metadata rows)
                    VANGUARDDD_<ts>.zip        (both files)
                    output/latest/             (mirror)
```

---

## 8. Known Gotchas & Important Notes

### Navigation timing is critical
The `time.sleep(10)` after loading the base URL and `time.sleep(6)` after the hash URL are load-tested values. Reducing them risks the Angular SPA not finishing bootstrap and the portfolio section not rendering. Do not shorten without testing.

### Playwright uses bundled Chromium
`playwright install chromium` downloads Chromium to `~/.cache/ms-playwright/`. The system's Chrome browser version is irrelevant — this is why Chrome auto-updates cannot break the scraper.

### Stealth must be applied before any navigation
`Stealth().apply_stealth_sync(page)` is called immediately after `context.new_page()` and before the first `page.goto()`. Applying it after navigation is too late — fingerprinting happens on page load.

### Master file must be closed in Excel before running
`openpyxl` cannot write to a file that Excel has open. If `save_master_data()` fails with a permission error, close the Excel file.

### tracking_state.json durations use CODE keys, not tickers
The comparison `scraped_durations != last_durations` works because both dicts use the same keys (`VANGUARDDD.INTERMEDIATETERMCORPORATEBONDETF.AVGDURATION.B` etc.). If you manually edit tracking_state.json, use those exact keys.

### Backfill updates existing rows in-place
`update_master_with_backfill` overwrites values from `as_of_date` row onwards, then appends any missing business days. This means historical correction is permanent and immediate.

### 2026-08-24 (Monday) is missing from master
This gap was caused by crashed Selenium/undetected-chromedriver attempts that day — the scraper never completed to reach the parser. The gap is permanent and harmless.

---

## 9. How to Add a New ETF Ticker

1. **`config.py` — add URL:**
   ```python
   URLS['VCSB'] = f'{VANGUARD_BASE_URL}/vcsb'
   ```

2. **`config.py` — add OUTPUT_COLUMNS entry** (append to end to avoid shifting existing columns):
   ```python
   OUTPUT_COLUMNS.append({
       'code':          'VANGUARDDD.NEWETF.AVGDURATION.B',
       'code_mnemonic': 'VANGUARDDD.NEWETF.AVGDURATION',
       'description':   'Vanguard New ETF, Portfolio composition, Average duration',
       'product':       'VCSB',
       'url_key':       'VCSB',
       'unit':          'years',
       'metric':        'Average duration',
       'fund_name':     'Vanguard New ETF'
   })
   ```

3. **`Master/Master_DATA.xlsx` — add a new column** after the existing three, with matching CODE in row 0 and description in row 1, and backfill historical values.

4. **`tracking_state.json` — add the new code key** to the `durations` dict with the current known value.

---

## 10. How to Update CSS Selectors (if Vanguard changes HTML)

All selectors live in `config.py` `SELECTORS` dict. To find the correct new selector:

1. Open `https://investor.vanguard.com/investment-products/etfs/profile/vcsh#portfolio-composition` in Chrome DevTools
2. Find the Average Duration value in the DOM
3. Look for `data-rpa-tag-id` attribute — if it still exists, just update the value in `SELECTORS['symbol_avg_duration']`
4. For the date, inspect the paragraph containing "as of MM/DD/YYYY"

---

## 11. Standalone Component Testing

Each module can run independently for debugging:

```bash
# Test scraper alone (no file writes)
python scraper.py

# Test parser alone with mock data (reads/writes master + tracking)
python parser.py

# Test file generator alone (reads existing master, generates output files)
python file_generator.py
```

---

## 12. Requirements

```
playwright>=1.40.0         # Browser automation
playwright-stealth>=1.0.0  # Bot detection evasion
pandas>=2.0.0              # Data manipulation
openpyxl>=3.0.0            # Excel read/write
```

**After install:** `playwright install chromium`

---

## 13. Production State (as of 2026-08-25)

| Item | Value |
|------|-------|
| Master rows | 653 (2024-02-29 to 2026-08-25) |
| Current as_of_date | 2026-07-31 |
| VCIT duration | 6.0 years |
| VCSH duration | 2.7 years |
| VCLT duration | 11.8 years |
| Last run | 2026-08-25 09:12:36 |
| Browser stack | Playwright + playwright-stealth |
| Headless | False (visible browser) |

---

## 14. Scheduling

To run daily on Windows, use Task Scheduler:
- **Program:** `python`
- **Arguments:** `D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\orchestrator.py`
- **Start in:** `D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook`
- **Trigger:** Daily, weekdays only, target time shortly after Vanguard typically updates (e.g. 8:00 AM EST)

Set `HEADLESS_MODE = True` in `config.py` for unattended runs.
